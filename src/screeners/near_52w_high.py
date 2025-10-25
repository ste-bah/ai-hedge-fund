from .common import ScreenResult

def screen_near_52w_high(symbols: list[str], av_client, lookback_days: int = 252) -> list[ScreenResult]:
    out = []
    for sym in symbols:
        try:
            df = av_client.daily_adjusted(sym, outputsize="full").tail(lookback_days)
            cur = float(df["adj_close"].iloc[-1])
            high = float(df["adj_close"].max())
            if high <= 0: 
                continue
            proximity = cur / high
            score = 1.0 / max(1e-6, 1.0 - proximity)
            out.append(ScreenResult(sym, score, {"proximity": proximity}))
        except Exception:
            continue
    out.sort(key=lambda r: r.score, reverse=True)
    return out