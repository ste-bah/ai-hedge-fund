import pandas as pd
from .common import ScreenResult

def _enterprise_value(overview: dict, balance: dict) -> float:
    try:
        mktcap = float(overview.get("MarketCapitalization", 0.0))
    except Exception:
        mktcap = 0.0
    ann = (balance.get("annualReports") or balance.get("annualReports", []))
    if ann:
        latest = ann[0]
        total_debt = float(latest.get("shortTermDebt", 0) or 0) + float(latest.get("longTermDebt", 0) or 0)
        cash = float(latest.get("cashAndCashEquivalentsAtCarryingValue", 0) or 0)
    else:
        total_debt, cash = 0.0, 0.0
    return max(mktcap + total_debt - cash, 0.0)

def magic_formula_score(overview: dict, income: dict, balance: dict) -> dict:
    ann_is = income.get("annualReports", [])
    ann_bs = balance.get("annualReports", [])
    if not ann_is or not ann_bs:
        return {"ey": 0.0, "roic": 0.0, "ev": 0.0}
    is_latest, bs_latest = ann_is[0], ann_bs[0]
    try:
        ebit = float(is_latest.get("operatingIncome", 0) or 0)
    except Exception:
        ebit = 0.0
    ev = _enterprise_value(overview, balance)
    ey = (ebit / ev) if ev > 0 else 0.0
    try:
        total_assets = float(bs_latest.get("totalAssets", 0) or 0)
        current_liab = float(bs_latest.get("totalCurrentLiabilities", 0) or 0)
        invested_capital = max(total_assets - current_liab, 1.0)
        roic = ebit / invested_capital
    except Exception:
        roic = 0.0
    return {"ey": ey, "roic": roic, "ev": ev}

def screen_magic_formula(symbols: list[str], av_client) -> list[ScreenResult]:
    rows = []
    for sym in symbols:
        try:
            ov = av_client.overview(sym)
            inc = av_client.income_statement(sym)
            bal = av_client.balance_sheet(sym)
            m = magic_formula_score(ov, inc, bal)
            score = 0.5 * m["ey"] + 0.5 * m["roic"]
            rows.append(ScreenResult(sym, score, {"ey": m["ey"], "roic": m["roic"], "ev": m["ev"]}))
        except Exception:
            continue
    rows.sort(key=lambda r: r.score, reverse=True)
    return rows