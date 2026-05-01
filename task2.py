# ============================================================
# TASK 2 — Live Market Data Fetch
# Timecell.ai Internship Assessment
# Author: Dhruvi
# AI Tools Used: Claude (Anthropic) ,chatgpt— error handling patterns,
#                retry logic structure, IST timezone handling
#
# APIs Used (all free, no key required):
#   - yfinance   → NIFTY50 index + Gold futures + USD/INR forex
#   - CoinGecko  → Bitcoin price
# ============================================================

import yfinance as yf
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

# ============================================================
# CONSTANTS
# ============================================================

REQUEST_TIMEOUT = 10      # seconds before a request is abandoned
MAX_RETRIES     = 2       # number of retry attempts per fetch
RETRY_DELAY     = 1       # seconds between retries

# Indian Standard Time = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


# ============================================================
# HELPER — Generic retry wrapper
# ============================================================

def with_retry(func, label: str):
    """
    Retries a callable up to MAX_RETRIES times.
    Logs each failure with the asset label.

    Args:
        func: Zero-argument callable that returns the result
        label: Asset name for error messages

    Returns:
        Result of func(), or raises the last exception
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(f"  ↩️  [{label}] Attempt {attempt} failed — retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    raise last_error


# ============================================================
# FETCHERS — One function per data source
# ============================================================

def fetch_nifty50() -> Optional[Dict]:
    """
    Fetches NIFTY 50 index price via yfinance (Yahoo Finance).
    Falls back to historical close if live price is unavailable.
    """
    try:
        ticker = yf.Ticker("^NSEI")

        def get_price() -> float:
            price = getattr(ticker.fast_info, "last_price", None)
            if price is None:
                # Fallback: use last available close price
                price = ticker.history(period="1d")["Close"].iloc[-1]
            if price is None:
                raise ValueError("NIFTY50 price is None after fallback")
            return float(price)

        price = with_retry(get_price, "NIFTY50")
        return {"asset": "NIFTY 50", "price": round(price, 2), "currency": "INR"}

    except Exception as e:
        print(f"  ❌  [ERROR] NIFTY50 fetch failed: {e}")
        return None


def fetch_bitcoin() -> Optional[Dict]:
    """
    Fetches Bitcoin (BTC) price in USD via CoinGecko public API.
    No API key required. Rate limit: ~30 calls/min on free tier.
    """
    url    = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}

    try:
        def get_price() -> float:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            price = response.json().get("bitcoin", {}).get("usd")
            if price is None:
                raise ValueError("BTC price key missing in response")
            return float(price)

        price = with_retry(get_price, "BTC")
        return {"asset": "BTC", "price": round(price, 2), "currency": "USD"}

    except requests.exceptions.Timeout:
        print("  ❌  [ERROR] BTC: CoinGecko request timed out")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"  ❌  [ERROR] BTC: HTTP {e.response.status_code} from CoinGecko")
        return None
    except Exception as e:
        print(f"  ❌  [ERROR] BTC fetch failed: {e}")
        return None


def fetch_gold_inr() -> Optional[Dict]:
    """
    Fetches Gold price in INR per gram.
    Method: Gold futures (GC=F, USD/troy oz) × USD/INR rate ÷ 31.1035 g/oz
    Both tickers from yfinance — no paid subscription needed.
    """
    try:
        gold_ticker  = yf.Ticker("GC=F")       # Gold futures in USD/troy oz
        forex_ticker = yf.Ticker("USDINR=X")   # USD to INR exchange rate

        def get_gold_usd() -> float:
            price = getattr(gold_ticker.fast_info, "last_price", None)
            if price is None:
                price = gold_ticker.history(period="1d")["Close"].iloc[-1]
            return float(price)

        def get_usd_inr() -> float:
            rate = getattr(forex_ticker.fast_info, "last_price", None)
            if rate is None:
                rate = forex_ticker.history(period="1d")["Close"].iloc[-1]
            return float(rate)

        gold_usd_per_oz  = with_retry(get_gold_usd, "GOLD-USD")
        usd_to_inr_rate  = with_retry(get_usd_inr,  "USD/INR")

        # Convert: USD per troy oz → INR per gram
        gold_inr_per_gram = (gold_usd_per_oz * usd_to_inr_rate) / 31.1035

        return {"asset": "GOLD", "price": round(gold_inr_per_gram, 2), "currency": "INR/g"}

    except Exception as e:
        print(f"  ❌  [ERROR] GOLD fetch failed: {e}")
        return None


# ============================================================
# TABLE RENDERER — Pure Python, no tabulate/pandas
# ============================================================

def print_price_table(results: List[Dict], fetch_time: str):
    """
    Renders a clean box-drawing table to the terminal.
    Column widths are fixed for consistent alignment.

    Args:
        results:    List of asset dicts with asset, price, currency
        fetch_time: Formatted timestamp string
    """
    COL_ASSET    = 12
    COL_PRICE    = 16
    COL_CURRENCY = 10

    def hline(left, mid, right, fill="─"):
        return (left + fill * COL_ASSET +
                mid  + fill * COL_PRICE +
                mid  + fill * COL_CURRENCY + right)

    top    = hline("┌", "┬", "┐")
    header = (f"│{'Asset'.center(COL_ASSET)}"
              f"│{'Price'.center(COL_PRICE)}"
              f"│{'Currency'.center(COL_CURRENCY)}│")
    divider = hline("├", "┼", "┤")
    bottom  = hline("└", "┴", "┘")

    print(f"\n  Asset Prices — fetched at {fetch_time} IST\n")
    print(f"  {top}")
    print(f"  {header}")
    print(f"  {divider}")

    for item in results:
        asset    = item["asset"].center(COL_ASSET)
        price    = f"{item['price']:>14,.2f}  "   # right-aligned number
        currency = item["currency"].center(COL_CURRENCY)
        print(f"  │{asset}│{price}│{currency}│")

    print(f"  {bottom}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("\n  🔄  Fetching live market data...")
    print("  " + "-" * 42)

    fetch_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    # All fetchers in one list — easy to add more later
    fetchers = [
        ("NIFTY50", fetch_nifty50),
        ("BTC",     fetch_bitcoin),
        ("GOLD",    fetch_gold_inr),
    ]

    results = []
    for name, fetcher in fetchers:
        result = fetcher()
        if result is not None:
            results.append(result)

    # Sort alphabetically for consistent output
    results.sort(key=lambda x: x["asset"])

    if results:
        print_price_table(results, fetch_time)
    else:
        print("\n  ❌  All fetches failed. Check your internet connection.")

    # Summary line
    total   = len(fetchers)
    success = len(results)
    failed  = total - success

    status = f"✅  {success}/{total} assets fetched successfully"
    if failed:
        status += f"  |  ⚠️  {failed} failed (see errors above)"

    print(f"\n  {status}\n")