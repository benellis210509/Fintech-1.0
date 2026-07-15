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
        cursor.execute(
            """
            SELECT last_update, data
            FROM market_cache
            WHERE ticker = ?
            """,
            (ticker.upper(),),
        )

        row = cursor.fetchone()

        if not row or not _cache_fresh(row["last_update"]):
            return None

        data = json.loads(row["data"])

        # Do not reuse broken cached results with no valid price.
        if float(data.get("price") or 0) <= 0:
            return None

        return data

    except Exception:
        return None

    finally:
        conn.close()


def _set_cached(ticker, data):
    # Never cache a failed result with a zero or missing price.
    if float(data.get("price") or 0) <= 0:
        return

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO market_cache (
                ticker,
                last_update,
                data
            )
            VALUES (?, ?, ?)
            """,
            (
                ticker.upper(),
                datetime.now().strftime("%Y-%m-%d"),
                json.dumps(data),
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()

    finally:
        conn.close()


def _safe_float(value):
    try:
        if value is None:
            return None

        number = float(value)

        if number != number:
            return None

        return number

    except (TypeError, ValueError):
        return None


def _get_price_from_fast_info(stock):
    try:
        fast_info = stock.fast_info

        price = (
            fast_info.get("last_price")
            or fast_info.get("regular_market_price")
            or fast_info.get("previous_close")
        )

        price = _safe_float(price)

        if price and price > 0:
            return price

    except Exception:
        pass

    return None


def _get_price_from_history(stock):
    try:
        history = stock.history(
            period="5d",
            interval="1d",
            auto_adjust=False,
        )

        if history is None or history.empty or "Close" not in history:
            return None

        close = history["Close"].dropna()

        if close.empty:
            return None

        price = _safe_float(close.iloc[-1])

        if price and price > 0:
            return price

    except Exception:
        pass

    return None


def fetch_ticker_data(ticker):
    ticker = str(ticker).strip().upper()

    if not ticker:
        return None

    cached = _get_cached(ticker)

    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)

        # Try the lighter and more reliable price sources first.
        price = _get_price_from_fast_info(stock)

        if not price:
            price = _get_price_from_history(stock)

        # Company details and ratios may still come from info.
        try:
            info = stock.info or {}
        except Exception:
            info = {}

        if not price:
            price = _safe_float(
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
            )

        # A ticker is not considered usable unless a valid price is found.
        if not price or price <= 0:
            print(
                "Market data warning for {}: no valid price returned.".format(
                    ticker
                )
            )
            return None

        company_name = (
            info.get("shortName")
            or info.get("longName")
            or ticker
        )

        data = {
            "ticker": ticker,
            "company_name": str(company_name),
            "price": float(price),
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "dividend_yield": _safe_float(info.get("dividendYield")),
            "beta": _safe_float(info.get("beta")),
            "sector": info.get("sector") or "Unknown Sector",
            "currency": info.get("currency") or "",
        }

        _set_cached(ticker, data)

        return data

    except Exception as exc:
        print(
            "Market data warning for {}: {}".format(
                ticker,
                exc,
            )
        )
        return None


def get_price_history_return(ticker, period="1mo"):
    try:
        history = yf.Ticker(ticker).history(
            period=period,
            auto_adjust=False,
        )

        if history is None or history.empty or "Close" not in history:
            return None

        close = history["Close"].dropna()

        if len(close) < 2:
            return None

        start = _safe_float(close.iloc[0])
        end = _safe_float(close.iloc[-1])

        if start is None or end is None or start == 0:
            return None

        return ((end - start) / start) * 100

    except Exception as exc:
        print(
            "History warning for {}: {}".format(
                ticker,
                exc,
            )
        )
        return None