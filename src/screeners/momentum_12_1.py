from .common import ScreenResult
import numpy as np

def _mom_12_1(prices_df) -> float:
    s = prices_df["adj_close"].dropna()
    if len(s) < 260:
        return float("nan")
    r12 = s.iloc[-1] / s.iloc[-252] - 1.0
    r1 = s.iloc[-1] / s.iloc[-21] - 1.0
    return float(r12 - r1)

def screen_momentum(symbols: list[str], av_client) -> list[ScreenResult]:
    res = []
    for sym in symbols:
        try:
            df = av_client.daily_adjusted(sym, outputsize="full")
            m = _mom_12_1(df)
            if np.isfinite(m):
                res.append(ScreenResult(sym, m, {"mom_12_1": m}))
        except Exception:
            continue
    res.sort(key=lambda r: r.score, reverse=True)
    return res