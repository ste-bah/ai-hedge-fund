import os
from data.alpha_vantage import AlphaVantageClient

def usd_to_gbp(av: AlphaVantageClient, amount: float) -> float:
    base = os.getenv("BASE_CCY", "GBP").upper()
    if base == "GBP":
        rate = av.fx_rate("USD","GBP")
        return amount * rate
    return amount