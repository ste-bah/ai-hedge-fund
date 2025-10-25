# src/pipeline/buffett_stack.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import math

# ---------- Try repo-native tools.api; fall back to yfinance ----------
_HAS_TOOLS_API = True
try:
    from tools.api import (
        get_financial_metrics as _tools_get_financial_metrics,   # may exist
        get_market_cap as _tools_get_market_cap,                 # may exist
        get_price as _tools_get_price,                           # may exist
        search_line_items as _tools_search_line_items,           # may exist
    )
except Exception:
    _HAS_TOOLS_API = False
    _tools_get_financial_metrics = None
    _tools_get_market_cap = None
    _tools_get_price = None
    _tools_search_line_items = None

# Fallbacks via yfinance
try:
    import yfinance as yf  # type: ignore
    _HAS_YF = True
except Exception:
    _HAS_YF = False


def _yf_price(symbol: str) -> Optional[float]:
    if not _HAS_YF:
        return None
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="10d")["Close"]
        if len(h) >= 1:
            return float(h.iloc[-1])
    except Exception:
        pass
    return None


def _yf_market_cap(symbol: str) -> Optional[float]:
    if not _HAS_YF:
        return None
    try:
        t = yf.Ticker(symbol)
        info = t.get_info()
        return float(info.get("marketCap")) if info.get("marketCap") is not None else None
    except Exception:
        return None


def _normalize_index(s: str) -> str:
    return str(s).strip().lower().replace(" ", "").replace("_", "")


def _yf_statements(symbol: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"income": None, "balance": None, "cashflow": None, "info": {}}
    if not _HAS_YF:
        return out
    try:
        t = yf.Ticker(symbol)
        inc = t.financials
        bal = t.balance_sheet
        cas = t.cashflow
        info = {}
        try:
            info = t.get_info()
        except Exception:
            info = {}
        def norm_df(df):
            if df is None or df.empty:
                return None
            d = df.copy()
            d.index = [_normalize_index(i) for i in d.index]
            return d
        out["income"] = norm_df(inc)
        out["balance"] = norm_df(bal)
        out["cashflow"] = norm_df(cas)
        out["info"] = info or {}
    except Exception:
        pass
    return out


def _yf_financial_metrics(symbol: str) -> Dict[str, Any]:
    st = _yf_statements(symbol)
    info = st["info"] or {}
    inc = st["income"]; bal = st["balance"]; cas = st["cashflow"]
    def last_from(df, key_norm):
        try:
            if df is not None and key_norm in df.index and len(df.columns) > 0:
                return float(df.loc[key_norm].iloc[-1])
        except Exception:
            pass
        return None
    m: Dict[str, Any] = {}
    # Income
    m["totalRevenue"] = last_from(inc, "totalrevenue")
    m["grossProfit"] = last_from(inc, "grossprofit")
    m["operatingIncome"] = last_from(inc, "operatingincome")
    m["netIncome"] = last_from(inc, "netincome")
    m["interestExpense"] = last_from(inc, "interestexpense")
    # Balance
    m["totalDebt"] = last_from(bal, "totaldebt")
    m["totalShareholdersEquity"] = last_from(bal, "totalshareholdersequity") or last_from(bal, "totalstockholdersequity")
    m["cashAndCashEquivalents"] = last_from(bal, "cashandcashequivalents") or last_from(bal, "cashandcashequivalentsatcarryingvalue")
    # Cashflow
    m["operatingCashflow"] = last_from(cas, "operatingcashflow")
    m["capitalExpenditures"] = last_from(cas, "capitalexpenditure")
    # Overview-ish
    m["sharesOutstanding"] = info.get("sharesOutstanding")
    m["pe"] = info.get("trailingPE") or info.get("forwardPE")
    m["PriceToSalesRatioTTM"] = info.get("priceToSalesTrailing12Months")
    m["PriceToBookRatio"] = info.get("priceToBook")
    m["DividendYield"] = info.get("dividendYield")
    m["Sector"] = info.get("sector")
    m["Industry"] = info.get("industry")
    m["Name"] = info.get("longName") or info.get("shortName")
    m["Symbol"] = symbol
    return {k: v for k, v in m.items() if v is not None}


def _tools_or_yf_price(symbol: str) -> Optional[float]:
    if _tools_get_price:
        try: return _tools_get_price(symbol)
        except Exception: pass
    return _yf_price(symbol)


def _tools_or_yf_market_cap(symbol: str) -> Optional[float]:
    if _tools_get_market_cap:
        try: return _tools_get_market_cap(symbol)
        except Exception: pass
    return _yf_market_cap(symbol)


def _tools_or_yf_financial_metrics(symbol: str) -> Dict[str, Any]:
    if _tools_get_financial_metrics:
        try:
            d = _tools_get_financial_metrics(symbol) or {}
            if d: return d
        except Exception:
            pass
    return _yf_financial_metrics(symbol)


def _tools_or_yf_search_line_items(symbol: str, keys: list[str]) -> Dict[str, Any]:
    if _tools_search_line_items:
        try:
            d = _tools_search_line_items(symbol, keys) or {}
            if d: return d
        except Exception:
            pass
    st = _yf_statements(symbol)
    inc, bal, cas = st["income"], st["balance"], st["cashflow"]
    out: Dict[str, Any] = {}
    for k in keys:
        nk = _normalize_index(k)
        val = None
        for df in (inc, bal, cas):
            if df is not None and nk in df.index and len(df.columns) > 0:
                try:
                    val = float(df.loc[nk].iloc[-1]); break
                except Exception:
                    pass
        if val is None and nk == "sharesoutstanding":
            val = st["info"].get("sharesOutstanding")
        out[k] = val
    return out


# ---------- Try to import repo agents; if missing, define local fallbacks ----------
_HAVE_VAL_AGENT = True
try:
    from agents.valuation import run_valuation  # your repo may not have this
except Exception:
    _HAVE_VAL_AGENT = False

_HAVE_BUFFETT_AGENT = True
try:
    from agents.warren_buffett import warren_buffett_decide  # your repo may not have this
except Exception:
    _HAVE_BUFFETT_AGENT = False


# ---- local valuation fallback (Owner Earnings DCF) ----
def _safe(x: Optional[float]) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None

def _owner_earnings(line_items: Dict[str, Any]) -> Optional[float]:
    ocf = _safe(line_items.get("operatingCashflow"))
    capex = _safe(line_items.get("capitalExpenditures"))
    if ocf is None or capex is None:
        return None
    return ocf - abs(capex)

def _simple_dcf(oe_now: Optional[float], growth: float = 0.05, years: int = 7, discount: float = 0.10, terminal_mult: float = 12.0) -> Optional[float]:
    if oe_now is None:
        return None
    pv = 0.0
    oe = oe_now
    for t in range(1, years + 1):
        oe *= (1.0 + growth)
        pv += oe / ((1.0 + discount) ** t)
    term = (oe * terminal_mult) / ((1.0 + discount) ** years)
    return pv + term

def _local_run_valuation(symbol: str, price: Optional[float], market_cap: Optional[float], metrics: Dict[str, Any], line_items: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal, robust valuation if your repo's valuation agent isn't available.
    Uses Owner Earnings DCF with conservative defaults and derives market cap from price*shares if needed.
    """
    so = _safe(metrics.get("sharesOutstanding")) or _safe(line_items.get("sharesOutstanding"))
    mc = _safe(market_cap)
    if mc is None and price is not None and so is not None:
        mc = price * so

    oe = _owner_earnings({k: _safe(line_items.get(k) or metrics.get(k)) for k in ("operatingCashflow","capitalExpenditures")})
    # Heuristics: growth ~ 4–8% if revenue margin decent; else 3–4%
    gross = _safe(metrics.get("grossProfit")); rev = _safe(metrics.get("totalRevenue"))
    gross_margin = (gross / rev) if (gross is not None and rev not in (None, 0)) else None
    growth = 0.08 if (gross_margin is not None and gross_margin > 0.45) else 0.05
    dcf = _simple_dcf(oe, growth=growth, years=7, discount=0.10, terminal_mult=12.0)
    intrinsic = None
    if dcf is not None and so:
        intrinsic = dcf / so

    upside_pct = None
    if intrinsic is not None and price not in (None, 0):
        upside_pct = (intrinsic / price - 1.0) * 100.0

    return {
        "owner_earnings": oe,
        "dcf_value": dcf,
        "intrinsic_value": intrinsic,
        "upside_pct": upside_pct,
        "growth_assumption": growth,
        "gross_margin": gross_margin,
        "market_cap_used": mc,
        "shares_outstanding": so,
    }


# ---- local Buffett decision fallback ----
def _buffett_decide_local(symbol: str, price: Optional[float], valuation: Dict[str, Any], fundamentals: Dict[str, Any], line_items: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based Buffett-ish decision if your repo agent isn't available."""
    gm = ( _safe(fundamentals.get("grossProfit")) or _safe(line_items.get("grossProfit")) )
    rev = ( _safe(fundamentals.get("totalRevenue")) or _safe(line_items.get("totalRevenue")) or _safe(line_items.get("revenue")) )
    op_inc = ( _safe(fundamentals.get("operatingIncome")) or _safe(line_items.get("operatingIncome")) )
    int_exp = ( _safe(fundamentals.get("interestExpense")) or _safe(line_items.get("interestExpense")) )
    eq = ( _safe(fundamentals.get("totalShareholdersEquity")) or _safe(line_items.get("totalShareholdersEquity")) )
    debt = ( _safe(fundamentals.get("totalDebt")) or _safe(line_items.get("totalDebt")) )
    cash = ( _safe(fundamentals.get("cashAndCashEquivalents")) or _safe(line_items.get("cashAndCashEquivalents")) )
    so = ( _safe(fundamentals.get("sharesOutstanding")) or _safe(line_items.get("sharesOutstanding")) )

    gross_margin = (gm / rev) if (gm is not None and rev not in (None, 0)) else None
    roic = None
    if op_inc is not None and eq is not None:
        tax_rate = 0.25
        net_debt = None if (debt is None or cash is None) else (debt - cash)
        invested_cap = None if (net_debt is None or eq is None) else (net_debt + eq)
        if invested_cap not in (None, 0):
            roic = (op_inc * (1 - tax_rate)) / invested_cap

    oe = valuation.get("owner_earnings")
    iv = valuation.get("intrinsic_value")
    up = valuation.get("upside_pct")

    # Quality gates
    q_gm = (gross_margin is not None and gross_margin > 0.60)
    q_roic = (roic is not None and roic > 0.10)
    q_leverage = (debt is not None and cash is not None and (debt - cash) < (eq or math.inf))  # net debt < equity
    quality_ok = sum([q_gm, q_roic, q_leverage]) >= 2

    # Decision
    mos_ok = (up is not None and up >= 50.0)
    signal = "bullish" if (quality_ok and mos_ok) else ("neutral" if mos_ok else "bearish")

    reason_parts = []
    reason_parts.append(
        f"At today’s price, our conservative owner-earnings DCF implies intrinsic value ≈ {iv:.2f} per share."
        if isinstance(iv, (int, float)) else
        "DCF could not be fully computed; inputs partially missing."
    )
    if up is not None:
        reason_parts.append(f"Margin of safety ≈ {up:.1f}% vs. price.")
    if gross_margin is not None:
        reason_parts.append(f"Gross margin ≈ {gross_margin*100:.1f}% ({'strong' if q_gm else 'below our bar'}).")
    if roic is not None:
        reason_parts.append(f"ROIC ≈ {roic*100:.1f}% ({'healthy' if q_roic else 'weak'}).")
    if q_leverage:
        reason_parts.append("Balance sheet reasonable (net debt < equity).")
    else:
        reason_parts.append("Leverage flags: net debt heavy vs equity.")

    reasoning = (
        "In my view, the business should be valued on the durable earnings power of the enterprise. "
        + " ".join(reason_parts)
        + " I would only be interested where economics are simple, management is rational, and price "
          "offers a meaningful margin of safety."
    )

    return {
        "signal": signal,
        "confidence": "medium" if quality_ok else "low",
        "reasoning": reasoning,
    }


# ---------- Summary table helpers ----------
def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x*100:.2f}%"

def _mult(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2f}x"

def _num(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2f}"

def _icon(ok: Optional[bool], info: bool = False) -> str:
    if info:
        return "ℹ️ Info"
    if ok is None:
        return "—"
    return "✅ Pass" if ok else "❌ Fail"

def _nz(x: Optional[float]) -> Optional[float]:
    return None if x is None or x == 0 else x

def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    a = None if a is None else float(a)
    b = _nz(b)
    if a is None or b is None:
        return None
    return a / b

def _as_ratio(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    v = float(v)
    return v / 100.0 if v > 1.5 else v

def _pick(d: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except Exception:
                pass
    return None

def _compute_summary(fin: Dict[str, Any], lines: Dict[str, Any], price: Optional[float]) -> Tuple[str, int, int]:
    revenue = _pick(lines, "revenue", "totalRevenue") or _pick(fin, "revenue", "totalRevenue")
    gross = _pick(lines, "grossProfit") or _pick(fin, "grossProfit")
    op_inc = _pick(lines, "operatingIncome") or _pick(fin, "operatingIncome")
    net_inc = _pick(lines, "netIncome") or _pick(fin, "netIncome")
    ocf = _pick(lines, "operatingCashflow") or _pick(fin, "operatingCashflow")
    capex = _pick(lines, "capitalExpenditures") or _pick(fin, "capitalExpenditures")
    interest_exp = _pick(lines, "interestExpense") or _pick(fin, "interestExpense")
    equity = _pick(lines, "totalShareholdersEquity", "totalShareholderEquity") or \
             _pick(fin, "totalShareholdersEquity", "totalShareholderEquity")
    total_debt = _pick(lines, "totalDebt") or _pick(fin, "totalDebt")
    cash = _pick(lines, "cashAndCashEquivalents") or _pick(lines, "cashAndCashEquivalentsAtCarryingValue") or \
           _pick(fin, "cashAndCashEquivalents", "cashAndCashEquivalentsAtCarryingValue")
    shares = _pick(lines, "sharesOutstanding") or _pick(fin, "sharesOutstanding")
    pe_raw = _pick(fin, "pe", "pe_ratio", "PERatio")

    gross_margin = _safe_div(gross, revenue)
    fcf = None if ocf is None or capex is None else (ocf - abs(capex))
    fcf_margin = _safe_div(fcf, revenue)

    roic = _as_ratio(_pick(fin, "roic", "ROIC"))
    if roic is None:
        tax_rate = 0.25
        ebit = op_inc
        nopat = None if ebit is None else ebit * (1 - tax_rate)
        net_debt = None if total_debt is None or cash is None else (total_debt - cash)
        invested_cap = None if equity is None or net_debt is None else (equity + net_debt)
        roic = _safe_div(nopat, invested_cap)

    interest_cov = None
    if op_inc is not None and interest_exp not in (None, 0):
        interest_cov = op_inc / abs(interest_exp)

    pe = pe_raw
    if pe is None and price is not None and shares and net_inc:
        eps = _safe_div(net_inc, shares)
        pe = None if (eps is None or eps == 0) else price / eps

    pass_gm = None if gross_margin is None else (gross_margin > 0.60)
    pass_roic = None if roic is None else (roic > 0.10)
    pass_fcf = None if fcf_margin is None else (fcf_margin > 0.20)
    pass_ic = None if interest_cov is None else (interest_cov >= 3.0)

    tests = [pass_gm, pass_roic, pass_fcf, pass_ic]
    total = sum(1 for t in tests if t is not None)
    passed = sum(1 for t in tests if t is True)

    rows = [
        ("Gross Margin",  _pct(gross_margin), ">60%",     _icon(pass_gm)),
        ("ROIC",          _pct(roic),         ">10–12%",  _icon(pass_roic)),
        ("FCF Margin",    _pct(fcf_margin),   ">20%",     _icon(pass_fcf)),
        ("Interest Coverage", _mult(interest_cov), "≥3–4x", _icon(pass_ic)),
        ("P/E Ratio",     _num(pe),           "Info Only", _icon(None, info=True)),
        ("Overall Score", f"{passed}/{max(1,total)}", "3–4/4", "⚠️ Weak" if passed < 3 else "✅ Strong"),
    ]

    md = ["\n📊 **Summary Table**\n",
          "| Metric | Value | Target | Status |",
          "|---|---:|:---:|:---:|"]
    for m, v, tgt, st in rows:
        md.append(f"| {m} | {v} | {tgt} | {st} |")
    md.append("")
    return "\n".join(md), passed, max(1, total)


# ---------- Public output dataclass ----------
@dataclass
class BuffettStackOutput:
    symbol: str
    price: Optional[float]
    market_cap: Optional[float]
    intrinsic_value: Optional[float]
    mos_upside_pct: Optional[float]
    valuation: Dict[str, Any]
    buffett: Dict[str, Any]
    summary_md: str
    score_passes: int
    score_total: int


# ---------- Main adapter ----------
def evaluate_with_buffett_stack(symbol: str, analysis_days: int = 1095) -> Optional[BuffettStackOutput]:
    price = _tools_or_yf_price(symbol)
    mcap = _tools_or_yf_market_cap(symbol)
    fin = _tools_or_yf_financial_metrics(symbol) or {}
    line_keys = [
        "revenue", "grossProfit", "operatingIncome", "netIncome",
        "operatingCashflow", "capitalExpenditures",
        "totalDebt", "cashAndCashEquivalents", "totalShareholdersEquity",
        "sharesOutstanding", "interestExpense",
    ]
    lines = _tools_or_yf_search_line_items(symbol, line_keys) or {}

    if not fin and not lines and (price is None and mcap is None):
        return None

    # --- Valuation ---
    if _HAVE_VAL_AGENT:
        try:
            val = run_valuation(symbol=symbol, price=price, market_cap=mcap, metrics=fin, line_items=lines) or {}
        except Exception:
            val = _local_run_valuation(symbol, price, mcap, fin, lines)
    else:
        val = _local_run_valuation(symbol, price, mcap, fin, lines)

    mos_up = val.get("upside_pct") or val.get("mos_upside_pct")
    iv = val.get("intrinsic_value") or val.get("owner_earnings_dcf") or val.get("dcf_value")

    # --- Buffett decision ---
    if _HAVE_BUFFETT_AGENT:
        try:
            buff = warren_buffett_decide(symbol=symbol, price=price, valuation=val, fundamentals=fin, line_items=lines) or {}
        except Exception:
            buff = _buffett_decide_local(symbol, price, val, fin, lines)
    else:
        buff = _buffett_decide_local(symbol, price, val, fin, lines)

    # --- Summary table ---
    summary_md, passes, total = _compute_summary(fin, lines, price)

    return BuffettStackOutput(
        symbol=symbol,
        price=price,
        market_cap=mcap,
        intrinsic_value=iv,
        mos_upside_pct=mos_up,
        valuation=val,
        buffett=buff,
        summary_md=summary_md,
        score_passes=passes,
        score_total=total,
    )
