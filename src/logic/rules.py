# src/logic/rules.py
from __future__ import annotations

from typing import Dict, Any

DEFAULT_THRESHOLDS = {
    "ROIC_min": 0.12,           # ≥12%
    "ROE_min": 0.12,            # ≥12%
    "FCFMargin_min": 0.05,      # ≥5%
    "NetDebtToEBITDA_max": 2.5, # if we have EBITDA; else skip this rule
    "InterestCoverage_min": 4.0,# ≥4x
    "PB_max": 5.0,              # sanity check
    "PE_max": 40.0,             # sanity check
    "MOS_upside_min": 50.0,     # ≥50% expected upside
}

def quality_pass(metrics: Dict[str, Any], th=DEFAULT_THRESHOLDS) -> Dict[str, Any]:
    ok = True
    reasons = []

    def check(cond: bool, msg: str):
        nonlocal ok
        if not cond:
            ok = False
            reasons.append(msg)

    roic = metrics.get("ROIC")
    if roic is not None:
        check(roic >= th["ROIC_min"], f"ROIC<{th['ROIC_min']:.2f}")
    roe = metrics.get("ROE")
    if roe is not None:
        check(roe >= th["ROE_min"], f"ROE<{th['ROE_min']:.2f}")

    fcfm = metrics.get("FCFMargin")
    if fcfm is not None:
        check(fcfm >= th["FCFMargin_min"], f"FCF margin<{th['FCFMargin_min']:.2f}")

    ebitda = metrics.get("EBITDA")
    net_debt = metrics.get("NetDebt")
    if ebitda and ebitda > 0 and net_debt is not None:
        nd_e = net_debt / ebitda
        check(nd_e <= th["NetDebtToEBITDA_max"], f"NetDebt/EBITDA>{th['NetDebtToEBITDA_max']:.1f}")

    ic = metrics.get("InterestCoverage")
    if ic is not None:
        check(ic >= th["InterestCoverage_min"], f"InterestCoverage<{th['InterestCoverage_min']:.1f}")

    # sanity valuation checks (don’t hard fail if missing)
    pe = metrics.get("PE")
    if pe is not None:
        check(pe <= th["PE_max"], "PE too high")
    pb = metrics.get("PB")
    if pb is not None:
        check(pb <= th["PB_max"], "PB too high")

    return {"pass": ok, "reasons": reasons}

def mos_pass(upside_pct: float | None, th=DEFAULT_THRESHOLDS) -> Dict[str, Any]:
    if upside_pct is None:
        return {"pass": False, "reasons": ["No upside estimate"]}
    return {"pass": upside_pct >= th["MOS_upside_min"],
            "reasons": [] if upside_pct >= th["MOS_upside_min"] else [f"Upside<{th['MOS_upside_min']}%"]}
