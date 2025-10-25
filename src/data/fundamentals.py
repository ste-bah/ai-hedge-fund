# src/data/fundamentals.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import pandas as pd

from data.alpha_vantage import AlphaVantageClient

_CACHE_DIR = Path(os.getenv("AV_CACHE_DIR", "./.av_cache"))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_TTL = 14 * 24 * 3600  # 14 days


def _cache_path(sym: str) -> Path:
    return _CACHE_DIR / f"fund_{sym}.json"


def _read_cache(sym: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(sym)
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text())
        if time.time() - obj.get("_ts", 0) <= _TTL:
            return obj.get("data")
    except Exception:
        return None
    return None


def _write_cache(sym: str, payload: Dict[str, Any]) -> None:
    try:
        _cache_path(sym).write_text(json.dumps({"_ts": time.time(), "data": payload}))
    except Exception:
        pass


def safe_float(x: Any, default: float | None = None) -> Optional[float]:
    try:
        if x is None or x == "" or (isinstance(x, str) and x.strip().lower() in {"none", "nan"}):
            return default
        return float(x)
    except Exception:
        return default


@dataclass
class Fundamentals:
    overview: Dict[str, Any]
    income_annual: pd.DataFrame
    balance_annual: pd.DataFrame
    cash_annual: pd.DataFrame
    earnings_annual: pd.DataFrame


def fetch_fundamentals(av: AlphaVantageClient, symbol: str, use_cache: bool = True) -> Optional[Fundamentals]:
    """
    Pull OVERVIEW, INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS.
    Returns None if nothing usable found.
    """
    if use_cache:
        c = _read_cache(symbol)
        if c:
            try:
                return Fundamentals(
                    overview=c["overview"],
                    income_annual=pd.DataFrame(c["income_annual"]),
                    balance_annual=pd.DataFrame(c["balance_annual"]),
                    cash_annual=pd.DataFrame(c["cash_annual"]),
                    earnings_annual=pd.DataFrame(c["earnings_annual"]),
                )
            except Exception:
                pass

    ov = av.company_overview(symbol) or {}
    inc = av.income_statement(symbol) or {}
    bal = av.balance_sheet(symbol) or {}
    cas = av.cash_flow(symbol) or {}
    ern = av.earnings(symbol) or {}

    # Normalize annual DataFrames
    def to_df(o: Dict[str, Any], key: str) -> pd.DataFrame:
        arr = o.get(key) or []
        df = pd.DataFrame(arr)
        if not df.empty and "fiscalDateEnding" in df.columns:
            df["fiscalDateEnding"] = pd.to_datetime(df["fiscalDateEnding"], errors="coerce")
            df = df.dropna(subset=["fiscalDateEnding"]).sort_values("fiscalDateEnding")
            df.reset_index(drop=True, inplace=True)
        return df

    income_annual = to_df(inc, "annualReports")
    balance_annual = to_df(bal, "annualReports")
    cash_annual = to_df(cas, "annualReports")

    # EARNINGS returns annualEarnings with reportedEPS + fiscalDateEnding (string years)
    ea = pd.DataFrame(ern.get("annualEarnings") or [])
    if not ea.empty:
        # fiscalDateEnding can be "2023" or "2023-12-31"
        ea["fiscalDateEnding"] = pd.to_datetime(ea["fiscalDateEnding"], errors="coerce")
        ea = ea.dropna(subset=["fiscalDateEnding"]).sort_values("fiscalDateEnding")
        ea.reset_index(drop=True, inplace=True)

    if not ov and income_annual.empty and balance_annual.empty and cash_annual.empty and ea.empty:
        return None

    f = Fundamentals(ov, income_annual, balance_annual, cash_annual, ea)
    # Cache
    if use_cache:
        try:
            _write_cache(symbol, {
                "overview": ov,
                "income_annual": income_annual.to_dict(orient="list"),
                "balance_annual": balance_annual.to_dict(orient="list"),
                "cash_annual": cash_annual.to_dict(orient="list"),
                "earnings_annual": ea.to_dict(orient="list"),
            })
        except Exception:
            pass
    return f


def compute_metrics(f: Fundamentals, price: Optional[float]) -> Dict[str, Any]:
    """
    Compute Buffett-ish quality metrics and growth trends from fundamentals.
    Returns a dict of floats/flags; missing values are None.
    """
    out: Dict[str, Any] = {}
    ov = f.overview

    # Shares Outstanding / Market Cap / EV heuristics
    so = safe_float(ov.get("SharesOutstanding"))
    mc = safe_float(ov.get("MarketCapitalization"))
    ebitda = safe_float(ov.get("EBITDA"))
    pe = safe_float(ov.get("PERatio"))
    ps = safe_float(ov.get("PriceToSalesRatioTTM"))
    pb = safe_float(ov.get("PriceToBookRatio"))
    div_yld = safe_float(ov.get("DividendYield"))

    out.update({
        "SharesOutstanding": so, "MarketCap": mc, "EBITDA": ebitda,
        "PE": pe, "PS": ps, "PB": pb, "DividendYield": div_yld,
        "Sector": ov.get("Sector"), "Industry": ov.get("Industry"), "Name": ov.get("Name"),
        "Symbol": ov.get("Symbol"),
    })

    # 3y Revenue CAGR, EPS CAGR from annual statements/earnings
    def cagr(series: List[float]) -> Optional[float]:
        series = [x for x in series if x is not None]
        if len(series) < 2:
            return None
        start, end, n = series[0], series[-1], len(series) - 1
        if start in (0, None):
            return None
        return (end / start) ** (1.0 / n) - 1.0

    # Revenue CAGR (income_annual: totalRevenue)
    revs: List[Optional[float]] = []
    if not f.income_annual.empty and "totalRevenue" in f.income_annual.columns:
        for x in f.income_annual["totalRevenue"].tolist():
            revs.append(safe_float(x))
    out["RevenueCAGR3Y"] = cagr(revs[-4:])  # last 4 years -> 3 intervals

    # EPS CAGR (earnings_annual: reportedEPS)
    epss: List[Optional[float]] = []
    if not f.earnings_annual.empty and "reportedEPS" in f.earnings_annual.columns:
        for x in f.earnings_annual["reportedEPS"].tolist():
            epss.append(safe_float(x))
    out["EPSCAGR3Y"] = cagr(epss[-4:])

    # Margins (gross, operating) – last year
    def last_float(df: pd.DataFrame, col: str) -> Optional[float]:
        if df.empty or col not in df.columns:
            return None
        return safe_float(df[col].iloc[-1])

    gross = last_float(f.income_annual, "grossProfit")
    revenue = last_float(f.income_annual, "totalRevenue")
    opInc = last_float(f.income_annual, "operatingIncome")
    netInc = last_float(f.income_annual, "netIncome")

    out["GrossMargin"] = (gross / revenue) if (gross is not None and revenue) else None
    out["OpMargin"] = (opInc / revenue) if (opInc is not None and revenue) else None
    out["NetMargin"] = (netInc / revenue) if (netInc is not None and revenue) else None

    # FCF & FCF margin – last year
    ocf = last_float(f.cash_annual, "operatingCashflow")
    capex = last_float(f.cash_annual, "capitalExpenditures")
    fcf = None
    if ocf is not None and capex is not None:
        fcf = ocf - abs(capex)
    out["FCF"] = fcf
    out["FCFMargin"] = (fcf / revenue) if (fcf is not None and revenue) else None

    # Leverage & coverage – last year
    totalDebt = last_float(f.balance_annual, "totalDebt")
    cash = last_float(f.balance_annual, "cashAndCashEquivalentsAtCarryingValue")
    netDebt = (totalDebt - cash) if (totalDebt is not None and cash is not None) else None
    out["NetDebt"] = netDebt

    interestExp = last_float(f.income_annual, "interestExpense")
    ebit = None
    if opInc is not None:
        ebit = opInc  # approx
    out["InterestCoverage"] = (ebit / abs(interestExp)) if (ebit and interestExp and interestExp != 0) else None

    # ROE/ROIC approximations – last year
    equity = last_float(f.balance_annual, "totalShareholderEquity")
    out["ROE"] = (netInc / equity) if (netInc is not None and equity not in (None, 0)) else None

    # ROIC ~ NOPAT / (NetDebt + Equity); tax approx 25%
    tax_rate = 0.25
    if opInc is not None:
        nopat = opInc * (1 - tax_rate)
    else:
        nopat = None
    invested_cap = None
    if netDebt is not None and equity is not None:
        invested_cap = netDebt + equity
    out["ROIC"] = (nopat / invested_cap) if (nopat is not None and invested_cap not in (None, 0)) else None

    # Price and basic ratios reliant on price
    out["Price"] = price
    if price and so:
        out["ImpliedMarketCapFromPrice"] = price * so

    return out
