import os
import pandas as pd
import requests

from data.cache import get_cache
from data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
)

# Global cache instance
_cache = get_cache()


def get_prices(ticker: str, start_date: str, end_date: str) -> list[Price]:
    """Fetch price data from cache or API."""
    # Check cache first
    if cached_data := _cache.get_prices(ticker):
        # Filter cached data by date range and convert to Price objects
        filtered_data = [Price(**price) for price in cached_data if start_date <= price["time"] <= end_date]
        if filtered_data:
            return filtered_data

    # If not in cache or no data in range, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    try:
        response = requests.get(url, headers=headers, timeout=30, verify=True)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Check specifically for 400 Bad Request, which might indicate missing data for this ticker
        if e.response.status_code == 400:
            print(f"Warning: No price data available for ticker {ticker}. The API returned a 400 Bad Request error.")
            return []  # Return empty list to allow processing to continue
        # For other HTTP errors, re-raise with more context
        raise Exception(f"HTTP error fetching prices for {ticker}: {e}")
    except requests.exceptions.RequestException as e:
        # Catch other potential request errors (including SSLError, Timeout, ConnectionError)
        raise Exception(f"Error fetching prices for {ticker}: {e}")

    # Parse response with Pydantic model
    price_response = PriceResponse(**response.json())
    prices = price_response.prices

    if not prices:
        return []

    # Cache the results as dicts
    _cache.set_prices(ticker, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API."""
    # Check cache first
    if cached_data := _cache.get_financial_metrics(ticker):
        # Filter cached data by date and limit
        filtered_data = [FinancialMetrics(**metric) for metric in cached_data if metric["report_period"] <= end_date]
        filtered_data.sort(key=lambda x: x.report_period, reverse=True)
        if filtered_data:
            return filtered_data[:limit]

    # If not in cache or insufficient data, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    try:
        # Add explicit timeout and verification
        response = requests.get(url, headers=headers, timeout=30, verify=True)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
    except requests.exceptions.HTTPError as e:
        # Check specifically for 400 Bad Request, which might indicate missing data for this ticker
        if e.response.status_code == 400:
            print(f"Warning: No financial metrics data available for ticker {ticker}. The API returned a 400 Bad Request error.")
            return []  # Return empty list to allow processing to continue with other tickers
        # For other HTTP errors, re-raise with more context
        raise Exception(f"HTTP error fetching financial metrics for {ticker}: {e}") from e
    except requests.exceptions.RequestException as e:
        # Catch other potential request errors (including SSLError, Timeout, ConnectionError)
        raise Exception(f"Error fetching financial metrics for {ticker}: {e}") from e

    # Parse response with Pydantic model
    metrics_response = FinancialMetricsResponse(**response.json())
    # Return the FinancialMetrics objects directly instead of converting to dict
    financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    # Cache the results as dicts
    _cache.set_financial_metrics(ticker, [m.model_dump() for m in financial_metrics])
    return financial_metrics


import time
import random

def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
) -> list[LineItem]:
    """Fetch line items from API."""
    # If not in cache or insufficient data, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    
    # Implement retry logic with exponential backoff
    max_retries = 3
    retry_delay = 2  # Initial delay in seconds
    
    for retry_count in range(max_retries + 1):
        try:
            # Ensure SSL verification is enabled (default)
            response = requests.post(url, headers=headers, json=body, timeout=30, verify=True) 
            response.raise_for_status() # Check for HTTP errors
            break  # Success, exit the retry loop
        except requests.exceptions.HTTPError as e:
            # Check specifically for 400 Bad Request, which might indicate missing data
            if e.response.status_code == 400:
                print(f"Warning: No line items data available for ticker {ticker}. The API returned a 400 Bad Request error.")
                return []  # Return empty list to allow processing to continue
            
            # Handle rate limiting (429 Too Many Requests)
            if e.response.status_code == 429:
                if retry_count < max_retries:
                    # Add jitter to avoid synchronized retries
                    jitter = random.uniform(0, 0.5)
                    sleep_time = retry_delay * (2 ** retry_count) + jitter
                    print(f"Rate limited when fetching line items for {ticker}. Retrying in {sleep_time:.2f} seconds (attempt {retry_count + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                    continue  # Retry after waiting
                else:
                    print(f"Warning: Rate limit exceeded for {ticker} after {max_retries} retries. Skipping line items.")
                    return []  # Return empty list after exhausting retries
            
            # For other HTTP errors, re-raise with more context
            raise Exception(f"HTTP error fetching line items for {ticker}: {e}") from e
        except requests.exceptions.RequestException as e:
            # For network errors, retry with backoff if we haven't exhausted retries
            if retry_count < max_retries:
                # Add jitter to avoid synchronized retries
                jitter = random.uniform(0, 0.5)
                sleep_time = retry_delay * (2 ** retry_count) + jitter
                print(f"Network error when fetching line items for {ticker}. Retrying in {sleep_time:.2f} seconds (attempt {retry_count + 1}/{max_retries})...")
                time.sleep(sleep_time)
                continue  # Retry after waiting
            
            # Catch other potential request errors (including SSLError, Timeout, ConnectionError)
            raise Exception(f"Error fetching line items for {ticker} after {max_retries} retries: {e}") from e
        
    data = response.json()
    response_model = LineItemResponse(**data)
    search_results = response_model.search_results
    if not search_results:
        return []

    # Cache the results
    return search_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    # Check cache first
    if cached_data := _cache.get_insider_trades(ticker):
        # Filter cached data by date range
        filtered_data = [InsiderTrade(**trade) for trade in cached_data 
                        if (start_date is None or (trade.get("transaction_date") or trade["filing_date"]) >= start_date)
                        and (trade.get("transaction_date") or trade["filing_date"]) <= end_date]
        filtered_data.sort(key=lambda x: x.transaction_date or x.filing_date, reverse=True)
        if filtered_data:
            return filtered_data

    # If not in cache or insufficient data, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    all_trades = []
    current_end_date = end_date
    
    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30, verify=True)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Check specifically for 400 Bad Request, which might indicate missing data for this ticker
            if e.response.status_code == 400:
                print(f"Warning: No insider trades data available for ticker {ticker}. The API returned a 400 Bad Request error.")
                return []  # Return empty list to allow processing to continue
            # For other HTTP errors, re-raise with more context
            raise Exception(f"HTTP error fetching insider trades for {ticker}: {e}")
        except requests.exceptions.RequestException as e:
            # Catch other potential request errors (including SSLError, Timeout, ConnectionError)
            raise Exception(f"Error fetching insider trades for {ticker}: {e}")
        
        data = response.json()
        response_model = InsiderTradeResponse(**data)
        insider_trades = response_model.insider_trades
        
        if not insider_trades:
            break
            
        all_trades.extend(insider_trades)
        
        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break
            
        # Update end_date to the oldest filing date from current batch for next iteration
        current_end_date = min(trade.filing_date for trade in insider_trades).split('T')[0]
        
        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    # Cache the results
    _cache.set_insider_trades(ticker, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    # Check cache first
    if cached_data := _cache.get_company_news(ticker):
        # Filter cached data by date range
        filtered_data = [CompanyNews(**news) for news in cached_data 
                        if (start_date is None or news["date"] >= start_date)
                        and news["date"] <= end_date]
        filtered_data.sort(key=lambda x: x.date, reverse=True)
        if filtered_data:
            return filtered_data

    # If not in cache or insufficient data, fetch from API
    headers = {}
    if api_key := os.environ.get("FINANCIAL_DATASETS_API_KEY"):
        headers["X-API-KEY"] = api_key

    all_news = []
    current_end_date = end_date
    
    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30, verify=True)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Check specifically for 400 Bad Request, which might indicate missing data for this ticker
            if e.response.status_code == 400:
                print(f"Warning: No news data available for ticker {ticker}. The API returned a 400 Bad Request error.")
                return []  # Return empty list to allow processing to continue
            # For other HTTP errors, re-raise with more context
            raise Exception(f"HTTP error fetching news for {ticker}: {e}")
        except requests.exceptions.RequestException as e:
            # Catch other potential request errors (including SSLError, Timeout, ConnectionError)
            raise Exception(f"Error fetching news for {ticker}: {e}")
        
        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news
        
        if not company_news:
            break
            
        all_news.extend(company_news)
        
        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(company_news) < limit:
            break
            
        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(news.date for news in company_news).split('T')[0]
        
        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    # Cache the results
    _cache.set_company_news(ticker, [news.model_dump() for news in all_news])
    return all_news



def get_market_cap(
    ticker: str,
    end_date: str,
) -> float | None:
    """Fetch market cap from the API."""
    financial_metrics = get_financial_metrics(ticker, end_date)
    
    # Check if any financial metrics were returned
    if not financial_metrics:
        print(f"Warning: No financial metrics found for {ticker}, cannot determine market cap.")
        return None
        
    market_cap = financial_metrics[0].market_cap
    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    # Check if prices list is empty
    if not prices:
        # Return an empty DataFrame with expected columns
        return pd.DataFrame(columns=["time", "open", "close", "high", "low", "volume", "Date"]).set_index("Date")
        
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        prices = get_prices(ticker, start_date, end_date)
        return prices_to_df(prices)
    except Exception as e:
        print(f"Error getting price data for {ticker}: {e}")
        # Return an empty DataFrame with expected columns
        return pd.DataFrame(columns=["time", "open", "close", "high", "low", "volume", "Date"]).set_index("Date")
