# src/data/universe.py
from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from data.alpha_vantage import AlphaVantageClient
from data.prices import (
    get_change_percent_yf_verbose,
    get_change_percent_av_daily_adjusted_verbose,
    get_change_percent_av_global_quote_verbose,
)

# ---------------------------
# Simple on-disk cache for OVERVIEW calls
# ---------------------------
_CACHE_DIR = Path(os.getenv("AV_CACHE_DIR", "./.av_cache"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_SEC = 7 * 24 * 3600  # 7 days

def _overview_cache_path(symbol: str) -> Path:
    return _CACHE_DIR / f"overview_{symbol}.json"

def _overview_cache_get(symbol: str) -> Optional[Dict[str, Any]]:
    p = _overview_cache_path(symbol)
    if not p.exists():
        return None
    try:
        with p.open("r") as f:
            obj = json.load(f)
        if time.time() - obj.get("_ts", 0) < _CACHE_TTL_SEC:
            return obj.get("data")
    except Exception:
        return None
    return None

def _overview_cache_put(symbol: str, data: Dict[str, Any]) -> None:
    p = _overview_cache_path(symbol)
    try:
        with p.open("w") as f:
            json.dump({"_ts": time.time(), "data": data}, f)
    except Exception:
        pass

# ---------------------------
# Sector/industry normalization
# ---------------------------
_GICS_CANON: Dict[str, List[str]] = {
    "health": ["Health Care", "Healthcare"],
    "energy": ["Energy"],
    "metals": ["Materials", "Metals", "Metals & Mining", "Steel", "Aluminum", "Copper"],
    "defence": ["Aerospace & Defense", "Defense", "Aerospace"],
    "defense": ["Aerospace & Defense", "Defense", "Aerospace"],
}

def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())

def _sector_match(desired: List[str], sector: Optional[str], industry: Optional[str]) -> bool:
    if not sector and not industry:
        return False
    dkeys = {_norm_key(d) for d in desired}
    if sector:
        s_norm = _norm_key(sector)
        for d in dkeys:
            for cand in _GICS_CANON.get(d, []):
                if _norm_key(cand) == s_norm:
                    return True
    haystack = " ".join([sector or "", industry or ""]).lower()
    for d in dkeys:
        for cand in _GICS_CANON.get(d, []):
            if cand.lower() in haystack:
                return True
    return False

# ---------------------------
# Local seeds (no-network fallback)
# ---------------------------
LOCAL_SEEDS = {
    "Defence": ["LMT", "NOC", "GD", "RTX", "BA", "LHX", "TXT", "HII", "CW", "HEI", "TDG", "AXON"],
    "Energy": ["XOM", "CVX", "SLB", "HAL", "COP", "EOG"],
    "Health": ["JNJ", "PFE", "MRK", "UNH", "LLY", "ABBV"],
    "Metals": ["FCX", "BHP", "RIO", "VALE"],
}

def _norm_sym(x: str) -> str:
    return (x or "").strip().upper()

def discover_universe_for_sectors(
    av: AlphaVantageClient,
    sectors: Sequence[str],
    exchanges: Sequence[str],
    names_per_sector: int,
    pool_cap: int = 600,
    use_fast: bool = True,
) -> Dict[str, List[str]]:
    results: Dict[str, List[str]] = {}

    # Try LISTING_STATUS first (CSV)
    df = av.listing_status_csv(state="active")
    if df is None or df.empty:
        print("[universe] LISTING_STATUS empty/missing — using LOCAL seeds (no network movers).")
        for sector in sectors:
            tickers = LOCAL_SEEDS.get(sector, [])[: max(names_per_sector, 1) * 6]  # oversample pool
            print(f"[universe] {sector}: {len(tickers)} tickers (local_seed=True, no OVERVIEW calls)")
            results[sector] = tickers[: names_per_sector * 6]
        return results

    # Normalize columns the CSV should contain (symbol,name,exchange,assetType,ipoDate,delistingDate,status)
    for need in ("symbol", "name", "exchange", "assettype", "status"):
        if need not in df.columns:
            df[need] = None

    # Filter exchanges if provided
    if exchanges:
        ex_upper = {e.strip().upper() for e in exchanges}
        df = df[df["exchange"].astype(str).str.upper().isin(ex_upper)]

    # Cap pool size
    if pool_cap and len(df) > pool_cap:
        df = df.head(pool_cap)

    # Simple heuristic demo for Defence via name keywords.
    def is_defence_name(n: str) -> bool:
        n = (n or "").upper()
        keys = ("DEFENSE", "DEFENCE", "AEROSPACE", "WEAPON", "MILITARY", "SURVEILLANCE")
        return any(k in n for k in keys)

    for sector in sectors:
        if sector == "Defence":
            pool = df[df["name"].apply(is_defence_name)]
            pool_syms = pool["symbol"].astype(str).apply(_norm_sym).dropna().tolist()
            if not pool_syms:
                pool_syms = LOCAL_SEEDS.get("Defence", [])
        else:
            pool_syms = LOCAL_SEEDS.get(sector, [])

        # De-dup and truncate
        seen = set()
        dedup = []
        for s in pool_syms:
            if s and s not in seen:
                seen.add(s)
                dedup.append(s)

        take = min(len(dedup), max(names_per_sector, 1) * 6)
        print(f"[universe] {sector}: {take} tickers (local_seed={'False' if sector=='Defence' else 'True'})")
        results[sector] = dedup[:take]

    return results


# ---------------------------
# Fast screen with layered price sources: yfinance → AV daily → AV quote
# ---------------------------
def fast_screen_with_quotes(
    av: AlphaVantageClient,
    symbols: List[str],
    price_source: str = "alphavantage",
    pause_sec: float = 12.0,
) -> List[Tuple[str, float]]:
    """
    Fetch change% per symbol and rank.
    If price_source=='yfinance', try Yahoo first; on failure fall back to Alpha Vantage (daily_adjusted, then global_quote).
    If price_source=='alphavantage', skip Yahoo and use AV directly.
    Returns list[(symbol, change_percent_float)], sorted desc.
    """
    out: List[Tuple[str, float]] = []
    throttle_hits = 0

    for i, sym in enumerate(symbols, 1):
        print(f"[screen] [{i}/{len(symbols)}] QUOTE {price_source} {sym} …", flush=True)

        pct_val: Optional[float] = None
        source_note = ""

        # 1) Yahoo first (if requested)
        if price_source == "yfinance":
            pct_val, note = get_change_percent_yf_verbose(sym)
            if pct_val is not None:
                source_note = note
            else:
                print(f"  -> yfinance: {note}", flush=True)

        # 2) AV: TIME_SERIES_DAILY_ADJUSTED (fallback or primary for alphavantage mode)
        if pct_val is None:
            pct_val, note = get_change_percent_av_daily_adjusted_verbose(av, sym)
            if pct_val is not None:
                source_note = note
            else:
                if "throttled" in note:
                    print(f"  -> AV daily: {note}", flush=True)
                    throttle_hits += 1
                    break
                print(f"  -> AV daily: {note}", flush=True)

        # 3) AV: GLOBAL_QUOTE (last resort)
        if pct_val is None:
            pct_val, note = get_change_percent_av_global_quote_verbose(av, sym)
            if pct_val is not None:
                source_note = note
            else:
                if "throttled" in note:
                    print(f"  -> AV quote: {note}", flush=True)
                    throttle_hits += 1
                    break
                print(f"  -> AV quote: {note}", flush=True)

        if pct_val is not None:
            print(f"  -> OK {pct_val:.2f}% [{source_note}]", flush=True)
            out.append((sym, pct_val))

        if pause_sec and pause_sec > 0 and price_source == "alphavantage":
            # be polite if we are leaning on AV
            time.sleep(0.0)

    out.sort(key=lambda t: t[1], reverse=True)
    if throttle_hits:
        print(f"[screen] Stopped early due to AV throttling (hits={throttle_hits}). "
              f"Consider increasing --pause-sec or re-running later.", flush=True)
    return out
