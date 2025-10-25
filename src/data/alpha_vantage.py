# src/data/alpha_vantage.py
from __future__ import annotations

import csv
import io
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any, List

import pandas as pd
import requests

# --- Auto-load .env (dotenv if installed; otherwise minimal fallback) ---
def _load_env_fallback() -> None:
    for candidate in [Path(".env"), Path.cwd() / ".env"]:
        try:
            if candidate.exists():
                for line in candidate.read_text().splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()  # loads ./.env by default
except Exception:
    _load_env_fallback()

DEFAULT_BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageError(Exception):
    pass


@dataclass
class AlphaVantageClient:
    api_key: Optional[str] = None
    base_url: str = DEFAULT_BASE_URL
    pause_sec: float = 12.0      # ~5 calls/minute budget by default
    timeout_sec: float = 15.0    # network timeout per call
    max_retries: int = 3

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            raise AlphaVantageError("Missing ALPHAVANTAGE_API_KEY in env")
        self._session = requests.Session()
        self._last_call_ts = 0.0

    # ---- Internal helpers ----
    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_ts
        if elapsed < self.pause_sec:
            time.sleep(self.pause_sec - elapsed)

    def _get(self, params: Dict[str, str]) -> requests.Response:
        # Pace to respect free-tier limits
        self._respect_rate_limit()
        p = dict(params)
        p["apikey"] = self.api_key

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(self.base_url, params=p, timeout=self.timeout_sec)
                self._last_call_ts = time.time()
                return resp
            except requests.RequestException as e:
                last_exc = e
                time.sleep(min(self.pause_sec * attempt, 30))
        raise AlphaVantageError(f"Network error after retries: {last_exc}")

    # ---- CSV endpoint ----
    def listing_status_csv(self, state: str = "active", date: Optional[str] = None) -> pd.DataFrame:
        """
        LISTING_STATUS returns CSV; parse into DataFrame.
        If throttled/malformed, return empty DataFrame (caller can fallback).
        """
        params = {"function": "LISTING_STATUS"}
        if state:
            params["state"] = state   # 'active' or 'delisted'
        if date:
            params["date"] = date     # YYYY-MM-DD

        resp = self._get(params)
        txt = (resp.text or "").strip()

        # Throttle/Note: JSON is returned even for CSV functions
        if txt.startswith("{") or txt.startswith("["):
            return pd.DataFrame()

        try:
            buf = io.StringIO(txt)
            reader = csv.DictReader(buf)
            rows = list(reader)
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            # Normalize for robustness
            df.columns = [c.strip().lower() for c in df.columns]
            # Malformed cases seen when throttled
            if df.empty or df.shape[1] < 2 or list(df.columns) == ["{}"]:
                return pd.DataFrame()
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Quotes / prices ----
    def global_quote(self, symbol: str) -> Optional[Dict[str, str]]:
        """
        Returns:
          - dict with Global Quote fields on success
          - {'__note': '...'} if throttled (JSON Note)
          - {'__raw': <dict>} if unexpected dict shape (debug)
          - None if totally empty/unknown
        """
        params = {"function": "GLOBAL_QUOTE", "symbol": symbol}
        resp = self._get(params)
        try:
            data: Any = resp.json()
        except ValueError:
            return None
        if isinstance(data, dict) and "Note" in data:
            return {"__note": data["Note"]}
        if isinstance(data, dict) and "Global Quote" in data:
            q = data.get("Global Quote") or {}
            return q if q else None
        # unexpected dict shape → pass back for logging
        if isinstance(data, dict):
            return {"__raw": data}
        return None

    def daily_adjusted(self, symbol: str, outputsize: str = "compact") -> pd.DataFrame:
        """
        Returns TIME_SERIES_DAILY_ADJUSTED as a tidy DataFrame with columns:
        ['open','high','low','close','adj_close','volume','dividend','split_coeff'] sorted by date ASC.
        Empty DataFrame on throttle/error.
        """
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize,  # 'compact' (~100 days) or 'full'
        }
        resp = self._get(params)
        try:
            data = resp.json()
        except ValueError:
            return pd.DataFrame()

        if not isinstance(data, dict) or "Time Series (Daily)" not in data:
            # throttle or error returns {"Note": "..."} etc.
            return pd.DataFrame()

        ts = data.get("Time Series (Daily)") or {}
        if not isinstance(ts, dict) or not ts:
            return pd.DataFrame()

        # Normalize into DataFrame
        try:
            df = pd.DataFrame.from_dict(ts, orient="index")
            df.index.name = "date"
            df.reset_index(inplace=True)
            # rename columns
            rename_map = {
                "1. open": "open",
                "2. high": "high",
                "3. low": "low",
                "4. close": "close",
                "5. adjusted close": "adj_close",
                "6. volume": "volume",
                "7. dividend amount": "dividend",
                "8. split coefficient": "split_coeff",
            }
            df.rename(columns=rename_map, inplace=True)
            # cast types
            for col in ("open", "high", "low", "close", "adj_close", "dividend", "split_coeff"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "volume" in df.columns:
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            # sort oldest->newest
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).sort_values("date")
            df.reset_index(drop=True, inplace=True)
            return df
        except Exception:
            return pd.DataFrame()

    # ---- Movers ----
    def top_gainers_losers(self) -> Optional[Dict[str, List[Dict]]]:
        params = {"function": "TOP_GAINERS_LOSERS"}
        resp = self._get(params)
        try:
            data = resp.json()
        except ValueError:
            return None
        if not isinstance(data, dict) or "top_gainers" not in data:
            return None
        return data

    # ---- Fundamentals ----
    def company_overview(self, symbol: str) -> Optional[Dict[str, Any]]:
        params = {"function": "OVERVIEW", "symbol": symbol}
        resp = self._get(params)
        try:
            data = resp.json()
        except ValueError:
            return None
        if not isinstance(data, dict) or not data:
            return None
        # AV returns {} for invalid or throttled
        return data if "Symbol" in data or "Name" in data else None

    def income_statement(self, symbol: str) -> Optional[Dict[str, Any]]:
        params = {"function": "INCOME_STATEMENT", "symbol": symbol}
        resp = self._get(params)
        try:
            d = resp.json()
            return d if isinstance(d, dict) and d else None
        except Exception:
            return None

    def balance_sheet(self, symbol: str) -> Optional[Dict[str, Any]]:
        params = {"function": "BALANCE_SHEET", "symbol": symbol}
        resp = self._get(params)
        try:
            d = resp.json()
            return d if isinstance(d, dict) and d else None
        except Exception:
            return None

    def cash_flow(self, symbol: str) -> Optional[Dict[str, Any]]:
        params = {"function": "CASH_FLOW", "symbol": symbol}
        resp = self._get(params)
        try:
            d = resp.json()
            return d if isinstance(d, dict) and d else None
        except Exception:
            return None

    def earnings(self, symbol: str) -> Optional[Dict[str, Any]]:
        params = {"function": "EARNINGS", "symbol": symbol}
        resp = self._get(params)
        try:
            d = resp.json()
            return d if isinstance(d, dict) and d else None
        except Exception:
            return None
