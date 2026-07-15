# utils.py
import csv
import logging
import re
from datetime import datetime
from pathlib import Path


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def today():
    return datetime.now().strftime("%Y-%m-%d")


def timestamp_for_file():
    return datetime.now().strftime("%Y_%m_%d_%H%M%S")


def clean_ticker(value):
    if value is None:
        return ""
    text = str(value).strip().upper()
    text = re.sub(r"[^A-Z0-9.\-]", "", text)
    return text


def parse_number(value, default=0.0):
    if value is None or value == "":
        return default
    text = str(value).strip().replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return default


def get_value(row, possible_fields, default=""):
    lower_map = {str(k).strip().lower(): v for k, v in row.items()}
    for field in possible_fields:
        value = lower_map.get(field.lower())
        if value not in (None, ""):
            return value
    return default


def read_csv_rows(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_sample_csv(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ["Ticker", "Company", "Shares", "Price", "Value", "CostBasis", "Currency", "Account"],
        ["AAPL", "Apple Inc", "10", "200", "2000", "1800", "USD", "Sample"],
        ["MSFT", "Microsoft Corp", "5", "450", "2250", "2000", "USD", "Sample"],
        ["CASH", "Cash", "0", "0", "500", "500", "USD", "Sample"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def safe_div(a, b):
    try:
        return float(a) / float(b) if float(b) != 0 else 0.0
    except Exception:
        return 0.0


def format_currency(value, currency="NZD"):
    """Format money with an explicit currency code to avoid ambiguity."""
    code = str(currency or "NZD").strip().upper()
    try:
        return "{} {:,.2f}".format(code, float(value or 0))
    except Exception:
        return "{} 0.00".format(code)


def format_number(value, decimals=2):
    try:
        return ("{:,." + str(decimals) + "f}").format(float(value or 0))
    except Exception:
        return "0.00"
