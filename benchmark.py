from datetime import datetime

from config import BENCHMARK_TICKER
from database import get_setting
from yahoo_data import get_price_history_return

BENCHMARK_MAP = {
    "S&P 500": "^GSPC",
    "NASDAQ 100": "^NDX",
    "NZX 50": "^NZ50",
}


def get_selected_benchmark(user_id=None):
    selected = get_setting("benchmark", "S&P 500", user_id=user_id)
    return BENCHMARK_MAP.get(selected, BENCHMARK_TICKER), selected


def benchmark_snapshot(user_id=None):
    ticker, selected = get_selected_benchmark(user_id=user_id)
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "name": selected,
        "ticker": ticker,
        "return_1m": get_price_history_return(ticker, "1mo"),
        "return_3m": get_price_history_return(ticker, "3mo"),
        "return_1y": get_price_history_return(ticker, "1y"),
        "data_note": "Latest available third-party market data; values may be delayed or unavailable.",
    }
