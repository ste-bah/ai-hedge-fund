from .common import ScreenResult

def _to_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0

def piotroski_fscore(income: dict, balance: dict, cash: dict) -> int:
    ann_is, ann_bs, ann_cf = income.get("annualReports", []), balance.get("annualReports", []), cash.get("annualReports", [])
    if len(ann_is) < 2 or len(ann_bs) < 2 or len(ann_cf) < 2:
        return 0
    cur_is, prev_is = ann_is[0], ann_is[1]
    cur_bs, prev_bs = ann_bs[0], ann_bs[1]
    cur_cf = ann_cf[0]

    score = 0
    roa_cur = _to_float(cur_is.get("netIncome")) / max(_to_float(cur_bs.get("totalAssets")), 1.0)
    roa_prev = _to_float(prev_is.get("netIncome")) / max(_to_float(prev_bs.get("totalAssets")), 1.0)
    if roa_cur > 0: score += 1
    if roa_cur > roa_prev: score += 1
    if _to_float(cur_cf.get("operatingCashflow")) > 0: score += 1
    if _to_float(cur_is.get("netIncome")) < _to_float(cur_cf.get("operatingCashflow")): score += 1
    if _to_float(cur_bs.get("longTermDebt")) <= _to_float(prev_bs.get("longTermDebt")): score += 1
    cur_ratio_cur = _to_float(cur_bs.get("totalCurrentAssets")) / max(_to_float(cur_bs.get("totalCurrentLiabilities")), 1.0)
    cur_ratio_prev = _to_float(prev_bs.get("totalCurrentAssets")) / max(_to_float(prev_bs.get("totalCurrentLiabilities")), 1.0)
    if cur_ratio_cur > cur_ratio_prev: score += 1
    if _to_float(cur_is.get("commonStockSharesOutstanding")) <= _to_float(prev_is.get("commonStockSharesOutstanding")): score += 1
    gm_cur = (_to_float(cur_is.get("grossProfit")) - _to_float(cur_is.get("costOfRevenue"))) if cur_is.get("costOfRevenue") is not None else _to_float(cur_is.get("grossProfit"))
    gm_prev = (_to_float(prev_is.get("grossProfit")) - _to_float(prev_is.get("costOfRevenue"))) if prev_is.get("costOfRevenue") is not None else _to_float(prev_is.get("grossProfit"))
    s_cur = max(_to_float(cur_is.get("totalRevenue")), 1.0)
    s_prev = max(_to_float(prev_is.get("totalRevenue")), 1.0)
    if (gm_cur / s_cur) > (gm_prev / s_prev): score += 1
    if (s_cur / max(_to_float(cur_bs.get("totalAssets")),1.0)) > (s_prev / max(_to_float(prev_bs.get("totalAssets")),1.0)): score += 1
    return score

def screen_piotroski(symbols: list[str], av_client, min_score: int = 7) -> list[ScreenResult]:
    out = []
    for sym in symbols:
        try:
            is_, bs, cf = av_client.income_statement(sym), av_client.balance_sheet(sym), av_client.cash_flow(sym)
            f = piotroski_fscore(is_, bs, cf)
            if f >= min_score:
                out.append(ScreenResult(sym, float(f), {"fscore": f}))
        except Exception:
            continue
    out.sort(key=lambda r: r.score, reverse=True)
    return out