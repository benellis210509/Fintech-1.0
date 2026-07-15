from database import get_connection
from yahoo_data import fetch_ticker_data


def run_portfolio_analytics(snapshot_id, user_id=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM portfolio_snapshots WHERE id = ? AND (? IS NULL OR user_id = ?)",
            (snapshot_id, user_id, user_id),
        )
        snapshot = cursor.fetchone()
        if not snapshot:
            return {}

        cursor.execute(
            "SELECT * FROM holdings WHERE snapshot_id = ? ORDER BY market_value DESC",
            (snapshot_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    cash_balance = float(snapshot["cash_balance"] or 0)
    equity_value = float(snapshot["total_value"] or 0)
    total_portfolio_value = equity_value + cash_balance
    base_currency = snapshot["base_currency"] or "NZD"

    holdings = []
    sector_totals = {}
    dividend_income = 0.0

    for row in rows:
        holding = dict(row)
        market_value = float(holding.get("market_value") or 0)
        cost_basis = float(holding.get("cost_basis") or 0)
        weight = market_value / total_portfolio_value if total_portfolio_value else 0
        unrealized = market_value - cost_basis
        unrealized_pct = (unrealized / cost_basis * 100) if cost_basis else 0

        market_data = fetch_ticker_data(holding["ticker"]) or {}
        sector = market_data.get("sector") or holding.get("sector") or "Unknown Sector"
        dividend_yield = market_data.get("dividend_yield") or 0
        dividend_income += market_value * dividend_yield
        sector_totals[sector] = sector_totals.get(sector, 0.0) + market_value

        holdings.append({
            "ticker": holding.get("ticker"),
            "company_name": holding.get("company_name"),
            "shares": holding.get("shares"),
            "price": holding.get("price"),
            "market_value": market_value,
            "cost_basis": cost_basis,
            "weight": weight,
            "unrealized_gain_loss": unrealized,
            "unrealized_gain_loss_pct": unrealized_pct,
            "currency": holding.get("currency") or base_currency,
            "account": holding.get("account") or "",
            "sector": sector,
        })

    sector_weights = [
        {
            "sector": sector,
            "market_value": value,
            "weight": value / total_portfolio_value if total_portfolio_value else 0,
        }
        for sector, value in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    previous = get_previous_snapshot_summary(snapshot_id, user_id)
    snapshot_value_change = 0.0
    snapshot_value_change_pct = 0.0
    if previous:
        previous_total = float(previous["total_value"] or 0) + float(previous["cash_balance"] or 0)
        snapshot_value_change = total_portfolio_value - previous_total
        snapshot_value_change_pct = (
            snapshot_value_change / previous_total * 100 if previous_total else 0.0
        )

    return {
        "snapshot_id": snapshot_id,
        "snapshot_date": snapshot["snapshot_date"],
        "base_currency": base_currency,
        "cash_balance": cash_balance,
        "equity_value": equity_value,
        "total_portfolio_value": total_portfolio_value,
        "total_value": equity_value,
        "holdings_count": len(holdings),
        "holdings": holdings,
        "sector_weights": sector_weights,
        "dividend_income": round(dividend_income, 2),
        "portfolio_yield": round(
            (dividend_income / total_portfolio_value * 100) if total_portfolio_value else 0,
            2,
        ),
        # This is a change in uploaded account value, not investment performance.
        "mom_change_usd": snapshot_value_change,
        "mom_change_pct": snapshot_value_change_pct,
        "cash_weight": cash_balance / total_portfolio_value if total_portfolio_value else 0,
        "allocation_observations": build_allocation_observations(
            holdings, cash_balance, total_portfolio_value
        ),
    }


def get_previous_snapshot_summary(current_snapshot_id, user_id=None):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT total_value, cash_balance
            FROM portfolio_snapshots
            WHERE id < ? AND (? IS NULL OR user_id = ?)
            ORDER BY id DESC
            LIMIT 1
        """, (current_snapshot_id, user_id, user_id)).fetchone()
    finally:
        conn.close()


def build_allocation_observations(holdings, cash_balance, total_value):
    """Return factual concentration observations without trading instructions."""
    if not total_value:
        return []

    observations = []
    weights = sorted(
        ((holding["ticker"], holding["market_value"] / total_value) for holding in holdings),
        key=lambda item: item[1],
        reverse=True,
    )

    if weights:
        ticker, largest = weights[0]
        if largest >= 0.25:
            observations.append(
                "{} represents {:.1f}% of the uploaded portfolio value.".format(
                    ticker, largest * 100
                )
            )

    top_five = sum(weight for _, weight in weights[:5])
    if top_five >= 0.75:
        observations.append(
            "The five largest holdings represent {:.1f}% of the uploaded portfolio value.".format(
                top_five * 100
            )
        )

    cash_weight = cash_balance / total_value
    observations.append(
        "Cash represents {:.1f}% of the uploaded portfolio value.".format(cash_weight * 100)
    )

    if not observations:
        observations.append("No concentration observations were generated from this snapshot.")
    return observations
