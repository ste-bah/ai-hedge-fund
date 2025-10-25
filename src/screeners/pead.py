from .common import ScreenResult

def _earnings_surprise(latest_q: dict) -> float:
    try:
        actual = float(latest_q.get("reportedEPS"))
        est = float(latest_q.get("estimatedEPS"))
        if est == 0:
            return 0.0
        return (actual - est) / abs(est)
    except Exception:
        return 0.0

def screen_pead(symbols: list[str], av_client, min_surprise: float = 0.03) -> list[ScreenResult]:
    out = []
    for sym in symbols:
        try:
            e = av_client.earnings(sym)
            q = (e.get("quarterlyEarnings") or [])
            if not q:
                continue
            s = _earnings_surprise(q[0])
            if s >= min_surprise:
                out.append(ScreenResult(sym, s, {"eps_surprise": s, "fiscalDateEnding": q[0].get("fiscalDateEnding")}))
        except Exception:
            continue
    out.sort(key=lambda r: r.score, reverse=True)
    return out