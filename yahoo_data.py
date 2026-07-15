# yahoo_data.py
import json
from datetime import datetime, timedelta

import yfinance as yf

from config import YAHOO_REFRESH_DAYS
from database import get_connection


def _cache_fresh(last_update):
    try:
        dt = datetime.strptime(last_update, "%Y-%m-%d")
        return datetime.now() - dt <= timedelta(days=YAHOO_REFRESH_DAYS)
    except Exception:
        return False


def _get_cached(ticker):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT last_update, data FROM market_cache WHERE ticker = ?", (ticker.upper(),))
        row = cursor.fetchone()
        if not row or not _cache_fresh(row["last_update"]):
            return None
        return json.loads(row["data"])
    except Exception:
        return None
    finally:
        conn.close()


def _set_cached(ticker, data):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO market_cache (ticker, last_update, data)
            VALUES (?, ?, ?)
        """, (ticker.upper(), datetime.now().strftime("%Y-%m-%d"), json.dumps(data)))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def fetch_ticker_data(ticker):
    ticker = str(ticker).strip().upper()
    if not ticker:
        return None

    cached = _get_cached(ticker)
    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0
        data = {
            "ticker": ticker,
            "company_name": info.get("shortName") or info.get("longName") or "",
            "price": float(price or 0),
            "pe_ratio": float(info["trailingPE"]) if info.get("trailingPE") else None,
            "forward_pe": float(info["forwardPE"]) if info.get("forwardPE") else None,
            "dividend_yield": float(info["dividendYield"]) if info.get("dividendYield") else None,
            "beta": float(info["beta"]) if info.get("beta") else None,
            "sector": info.get("sector") or "Unknown Sector",
            "currency": info.get("currency") or "",
        }
        _set_cached(ticker, data)
        return data
    except Exception as exc:
        print("Market data warning for {}: {}".format(ticker, exc))
        return None


def get_price_history_return(ticker, period="1mo"):
    try:
        history = yf.Ticker(ticker).history(period=period)
        if history is None or history.empty or "Close" not in history:
            return None
        close = history["Close"].dropna()
        if len(close) < 2:
            return None
        start = float(close.iloc[0])
        end = float(close.iloc[-1])
        if start == 0:
            return None
        return ((end - start) / start) * 100
    except Exception as exc:
        print("History warning for {}: {}".format(ticker, exc))
        return None
