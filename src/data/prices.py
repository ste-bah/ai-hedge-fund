# src/data/prices.py
from __future__ import annotations

from typing import Optional, Tuple, List, Any

# Optional Yahoo alias map (share classes etc.)
_YF_ALIASES = {
    "HEI": ["HEI", "HEI-A"],
    # Add more if needed, e.g.:
    # "BRK.B": ["BRK-B", "BRK.B"],
    # "BF.B": ["BF-B", "BF.B"],
}

def _unique_candidates(symbol: str) -> List[str]:
    sym = (symbol or "").strip().upper()
    cands = [sym]
    for alt in _YF_ALIASES.get(sym, []):
        if alt not in cands:
            cands.append(alt)
    return cands

# ---------------------------
# Yahoo Finance (yfinance) % change
# ---------------------------
def get_change_percent_yf_verbose(symbol: str) -> Tuple[Optional[float], str]:
    """
    Try to compute % change using Yahoo Finance (yfinance), with diagnostics.
    Returns: (pct_change or None, note)
    """
    try:
        import yfinance as yf  # ensure: poetry add yfinance
    except Exception as e:
        return None, f"yfinance import failed: {e}"

    cands = _unique_candidates(symbol)

    # Try both download() and Ticker().history() for robustness.
    for cand in cands:
        try:
            df = yf.download(cand, period="7d", interval="1d", progress=False, auto_adjust=True)
            if df is not None and not df.empty and "Close" in df.columns:
                closes = df["Close"].dropna()
                if len(closes) >= 2:
                    last = float(closes.iat[-1])
                    prev = float(closes.iat[-2])
                    if prev != 0:
                        return ((last - prev) / prev) * 100.0, f"ok:download:{cand}"
        except Exception:
            pass

        try:
            t = yf.Ticker(cand)
            hist = t.history(period="7d", interval="1d", auto_adjust=True)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                closes = hist["Close"].dropna()
                if len(closes) >= 2:
                    last = float(closes.iat[-1])
                    prev = float(closes.iat[-2])
                    if prev != 0:
                        return ((last - prev) / prev) * 100.0, f"ok:history:{cand}"
        except Exception:
            pass

    return None, "yfinance: no data for symbol/aliases"

def get_change_percent_yf(symbol: str) -> Optional[float]:
    pct, _ = get_change_percent_yf_verbose(symbol)
    return pct

# ---------------------------
# Alpha Vantage % change from TIME_SERIES_DAILY_ADJUSTED
# ---------------------------
def get_change_percent_av_daily_adjusted_verbose(
    av_client: Any, symbol: str
) -> Tuple[Optional[float], str]:
    """
    Uses Alpha Vantage TIME_SERIES_DAILY_ADJUSTED to compute % change from last two closes.
    av_client must have: daily_adjusted(symbol, outputsize='compact') -> DataFrame with 'adj_close' or 'close'.
    """
    try:
        df = av_client.daily_adjusted(symbol, outputsize="compact")
    except Exception as e:
        return None, f"av: daily_adjusted error: {e}"

    if df is None or df.empty:
        return None, "av: daily_adjusted empty"

    col = "adj_close" if "adj_close" in df.columns else ("close" if "close" in df.columns else None)
    if not col:
        return None, "av: daily_adjusted missing close columns"

    closes = df[col].dropna()
    if len(closes) < 2:
        return None, "av: daily_adjusted not enough data"

    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2])
    if prev == 0:
        return None, "av: prev=0"
    return ((last - prev) / prev) * 100.0, "ok:av:daily_adjusted"

# ---------------------------
# Alpha Vantage % change from GLOBAL_QUOTE
# ---------------------------
def get_change_percent_av_global_quote_verbose(
    av_client: Any, symbol: str
) -> Tuple[Optional[float], str]:
    """
    Uses Alpha Vantage GLOBAL_QUOTE "10. change percent".
    av_client must have: global_quote(symbol) -> dict or {'__note': ...}
    """
    try:
        q = av_client.global_quote(symbol)
    except Exception as e:
        return None, f"av: global_quote error: {e}"

    if q is None:
        return None, "av: global_quote empty"
    if isinstance(q, dict) and "__note" in q:
        return None, f"av: throttled: {q['__note'][:80]}"

    pct_str = (q.get("10. change percent") or "").replace("%", "").strip() if isinstance(q, dict) else ""
    try:
        return float(pct_str), "ok:av:global_quote"
    except Exception:
        return None, "av: global_quote missing/invalid change percent"
