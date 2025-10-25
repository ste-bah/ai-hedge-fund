# src/logic/valuation.py
from __future__ import annotations

from typing import Dict, Any, Optional

def _clamp(x: Optional[float], lo: float, hi: float, default: float) -> float:
    if x is None:
        return default
    return max(lo, min(hi, x))

def dcf_lite(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Very conservative DCF-lite on FCF:
    - starting FCF = last year FCF (or EPS*CFO margin proxy if missing)
    - growth = min( max(RevenueCAGR3Y, 0%), 6% ), default 3%
    - discount rate = 10%
    - terminal growth = 2.5%
    - 5-year horizon
    Returns fair value per share if SharesOutstanding present, else fair value (EV-ish).
    """
    fcf = metrics.get("FCF")
    so = metrics.get("SharesOutstanding")
    price = metrics.get("Price")
    mc = metrics.get("MarketCap")

    g = _clamp(metrics.get("RevenueCAGR3Y"), -0.02, 0.06, 0.03)
    dr = 0.10
    tg = 0.025
    years = 5

    if fcf is None or fcf <= 0:
        return {"fv_base": None, "fv_ps": None, "upside_pct": None}

    # project
    f = fcf
    pv = 0.0
    for t in range(1, years + 1):
        f = f * (1 + g)
        pv += f / ((1 + dr) ** t)
    # terminal
    terminal = (f * (1 + tg)) / (dr - tg)
    pv_term = terminal / ((1 + dr) ** years)
    ev = pv + pv_term

    # Fair value per share
    fv_ps = (ev / so) if so and so > 0 else None

    # Upside vs price
    upside_pct = None
    if fv_ps and price and price > 0:
        upside_pct = (fv_ps / price - 1.0) * 100.0
    elif ev and mc and mc > 0:
        upside_pct = (ev / mc - 1.0) * 100.0

    return {
        "fv_base": ev,
        "fv_ps": fv_ps,
        "upside_pct": upside_pct,
        "assumptions": {"g": g, "dr": dr, "tg": tg, "years": years},
    }
