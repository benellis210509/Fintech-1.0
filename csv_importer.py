import logging
from pathlib import Path

from config import CSV_PATH, DEFAULT_CURRENCY, MAX_CSV_ROWS
from database import get_connection
from utils import clean_ticker, get_value, parse_number, read_csv_rows, today, write_sample_csv

TICKER_FIELDS = ["Ticker", "Symbol", "Code", "Instrument", "Security", "Asset"]
COMPANY_FIELDS = ["Company", "Company Name", "Name", "Description", "Security Name"]
SHARES_FIELDS = ["Shares", "Quantity", "Qty", "Units", "Holding Quantity", "Ending Share Holding Quantity"]
PRICE_FIELDS = ["Price", "Share Price", "Ending Share Price", "Last Price", "Market Price", "Current Price"]
VALUE_FIELDS = ["Value", "Market Value", "Ending Investment Dollar Value", "Investment Value", "Position Value", "Amount"]
COST_FIELDS = ["CostBasis", "Cost Basis", "Average Cost Basis", "Book Cost", "Cost", "Total Cost"]
CURRENCY_FIELDS = ["Currency", "CCY"]
ACCOUNT_FIELDS = ["Account", "Portfolio", "Wallet"]
SECTOR_FIELDS = ["Sector", "Industry"]


def import_csv(csv_path=CSV_PATH, user_id=None):
    """Import one single-currency broker CSV and return its snapshot id."""
    csv_path = Path(csv_path)

    if not csv_path.exists():
        write_sample_csv(csv_path)
        raise FileNotFoundError(
            "CSV file was missing, so a sample was created at {}.".format(csv_path)
        )

    rows = read_csv_rows(csv_path)
    if not rows:
        raise ValueError("The CSV file is empty.")
    if len(rows) > MAX_CSV_ROWS:
        raise ValueError("The CSV has too many rows. Maximum: {}.".format(MAX_CSV_ROWS))

    snapshot_date = today()
    cash_balance = 0.0
    equity_value = 0.0
    holdings = []
    skipped = []
    currencies = set()

    for idx, row in enumerate(rows, start=2):
        ticker = clean_ticker(get_value(row, TICKER_FIELDS))
        company = str(get_value(row, COMPANY_FIELDS, ticker or "Unknown")).strip()
        currency = str(get_value(row, CURRENCY_FIELDS, DEFAULT_CURRENCY) or DEFAULT_CURRENCY).strip().upper()
        account = str(get_value(row, ACCOUNT_FIELDS, "") or "").strip()
        sector = str(get_value(row, SECTOR_FIELDS, "Unknown Sector") or "Unknown Sector").strip()

        shares = parse_number(get_value(row, SHARES_FIELDS), 0.0)
        price = parse_number(get_value(row, PRICE_FIELDS), 0.0)
        market_value = parse_number(get_value(row, VALUE_FIELDS), 0.0)
        cost_basis = parse_number(get_value(row, COST_FIELDS), 0.0)

        if not ticker and company:
            ticker = clean_ticker(company)
        if not ticker:
            skipped.append("row {}: no ticker".format(idx))
            continue

        is_cash = ticker in ("CASH", "NZD", "USD", "AUD") or "cash" in company.lower()

        if market_value == 0 and shares and price:
            market_value = shares * price
        if cost_basis == 0 and market_value:
            cost_basis = market_value

        if market_value <= 0 and not is_cash:
            skipped.append("row {} {}: no market value".format(idx, ticker))
            continue

        currencies.add(currency)

        if is_cash:
            cash_balance += market_value or price or cost_basis
            continue

        equity_value += market_value
        holdings.append({
            "ticker": ticker,
            "company_name": company or ticker,
            "shares": shares,
            "price": price,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "currency": currency,
            "account": account,
            "sector": sector,
        })

    if not holdings and cash_balance <= 0:
        raise ValueError("No usable holdings were found. Check the CSV column names and values.")

    if len(currencies) > 1:
        raise ValueError(
            "Mixed-currency totals are not supported yet. Convert all money values to one base currency before uploading. Found: {}.".format(
                ", ".join(sorted(currencies))
            )
        )

    base_currency = next(iter(currencies), DEFAULT_CURRENCY)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO portfolio_snapshots (
                user_id, snapshot_date, cash_balance, total_value, source_file, base_currency
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, snapshot_date, cash_balance, equity_value, csv_path.name, base_currency))
        snapshot_id = cursor.lastrowid

        for holding in holdings:
            cursor.execute("""
                INSERT INTO holdings (
                    snapshot_id, ticker, company_name, shares, price, market_value,
                    cost_basis, currency, account, sector
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                holding["ticker"],
                holding["company_name"],
                holding["shares"],
                holding["price"],
                holding["market_value"],
                holding["cost_basis"],
                holding["currency"],
                holding["account"],
                holding["sector"],
            ))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logging.info(
        "Imported snapshot %s | holdings=%s | equity=%.2f | cash=%.2f | currency=%s",
        snapshot_id,
        len(holdings),
        equity_value,
        cash_balance,
        base_currency,
    )
    if skipped:
        logging.warning("Skipped CSV rows: %s", "; ".join(skipped[:10]))
    return snapshot_id


if __name__ == "__main__":
    print(import_csv())
