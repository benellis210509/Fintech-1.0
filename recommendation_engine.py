# recommendation_engine.py
from database import get_connection
from yahoo_data import fetch_ticker_data
from utils import today


def _classification(score):
    if score >= 78:
        return "Strong fundamentals"
    if score >= 65:
        return "Positive research signal"
    if score >= 52:
        return "Neutral research signal"
    if score >= 40:
        return "Cautious research signal"
    return "Data insufficient or weak signal"


def score_holding(holding):
    ticker = holding.get("ticker")
    data = fetch_ticker_data(ticker) or {}
    score = 50.0
    reasons = []

    pe = data.get("pe_ratio")
    if pe:
        if pe < 15:
            score += 12
            reasons.append("lower trailing P/E relative to common market ranges")
        elif pe < 30:
            score += 4
            reasons.append("moderate trailing P/E")
        else:
            score -= 10
            reasons.append("elevated trailing P/E")
    else:
        reasons.append("trailing P/E unavailable")

    forward_pe = data.get("forward_pe")
    if forward_pe and pe:
        if forward_pe < pe:
            score += 5
            reasons.append("forward P/E is below trailing P/E")
        elif forward_pe > pe * 1.15:
            score -= 4
            reasons.append("forward P/E is above trailing P/E")

    div_yield = data.get("dividend_yield")
    if div_yield and div_yield > 0.025:
        score += 5
        reasons.append("meaningful indicated dividend yield")

    beta = data.get("beta")
    if beta:
        if beta > 1.5:
            score -= 8
            reasons.append("higher market sensitivity")
        elif beta < 0.8:
            score += 4
            reasons.append("lower market sensitivity")

    weight = float(holding.get("weight") or 0)
    if weight > 0.30:
        score -= 14
        reasons.append("very high portfolio concentration")
    elif weight > 0.20:
        score -= 9
        reasons.append("high portfolio concentration")

    unrealized_pct = float(holding.get("unrealized_gain_loss_pct") or 0)
    if unrealized_pct > 50:
        score -= 3
        reasons.append("large reported unrealized gain")
    elif unrealized_pct < -30:
        score -= 5
        reasons.append("large reported unrealized loss")

    score = max(0, min(100, score))

    return {
        "ticker": ticker,
        "action": _classification(score),
        "classification": _classification(score),
        "confidence": round(score, 1),
        "score": round(score, 1),
        "reasoning": "; ".join(reasons) if reasons else "balanced mechanical score using available valuation, income, volatility and concentration data",
        "legal_note": "Research classification only. It is not a recommendation to buy, sell or hold.",
    }


def generate_recommendations(snapshot_id, summary, user_id=None):
    holdings = summary.get("holdings", [])
    recommendations = [score_holding(h) for h in holdings]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        for rec in recommendations:
            cursor.execute(
                """
                INSERT INTO recommendations (
                    user_id, snapshot_id, date, ticker,
                    action, confidence, reasoning
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    snapshot_id,
                    today(),
                    rec["ticker"],
                    rec["classification"],
                    rec["confidence"],
                    rec["reasoning"],
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return recommendations
