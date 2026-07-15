# portfolio_score.py

def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def score_to_grade(score):
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 85:
        return "A-"
    if score >= 80:
        return "B+"
    if score >= 75:
        return "B"
    if score >= 70:
        return "B-"
    if score >= 65:
        return "C+"
    if score >= 60:
        return "C"
    return "Needs Attention"


def score_to_label(score):
    if score >= 90:
        return "High structural score"
    if score >= 80:
        return "Above-average structural score"
    if score >= 70:
        return "Moderate structural score"
    if score >= 60:
        return "Lower structural score"
    return "Limited structural score"


def calculate_portfolio_score(
    holdings_count,
    cash_pct,
    largest_weight,
    allocation,
):
    """
    Produces a transparent portfolio-structure score.

    It measures only holding count, concentration, cash percentage and HHI.
    It does not assess suitability, goals, tax, liquidity needs, product quality,
    valuation, expected returns or future performance. It is not financial advice.
    """

    # -----------------------------------------
    # Diversification: 30 points
    # -----------------------------------------
    if holdings_count >= 15:
        holdings_score = 15
    elif holdings_count >= 10:
        holdings_score = 13
    elif holdings_count >= 7:
        holdings_score = 10
    elif holdings_count >= 4:
        holdings_score = 7
    elif holdings_count >= 2:
        holdings_score = 4
    else:
        holdings_score = 1

    if largest_weight <= 15:
        concentration_score = 15
    elif largest_weight <= 20:
        concentration_score = 13
    elif largest_weight <= 25:
        concentration_score = 10
    elif largest_weight <= 35:
        concentration_score = 6
    elif largest_weight <= 50:
        concentration_score = 3
    else:
        concentration_score = 0

    diversification = holdings_score + concentration_score

    # -----------------------------------------
    # Concentration risk: 25 points
    # -----------------------------------------
    weights = [
        float(item.get("weight") or 0)
        for item in allocation
    ]

    top_five_weight = sum(
        sorted(weights, reverse=True)[:5]
    )

    if top_five_weight <= 55:
        concentration = 25
    elif top_five_weight <= 65:
        concentration = 21
    elif top_five_weight <= 75:
        concentration = 16
    elif top_five_weight <= 85:
        concentration = 10
    else:
        concentration = 4

    # -----------------------------------------
    # Cash allocation: 20 points
    # -----------------------------------------
    if 5 <= cash_pct <= 15:
        cash_allocation = 20
    elif 2 <= cash_pct < 5:
        cash_allocation = 16
    elif 15 < cash_pct <= 25:
        cash_allocation = 15
    elif cash_pct < 2:
        cash_allocation = 10
    elif cash_pct <= 40:
        cash_allocation = 9
    else:
        cash_allocation = 4

    # -----------------------------------------
    # Portfolio spread: 25 points
    # -----------------------------------------
    if not weights:
        spread = 0
    else:
        hhi = sum((weight / 100) ** 2 for weight in weights)

        if hhi <= 0.10:
            spread = 25
        elif hhi <= 0.15:
            spread = 22
        elif hhi <= 0.20:
            spread = 18
        elif hhi <= 0.30:
            spread = 12
        else:
            spread = 6

    total_score = int(
        clamp(
            diversification
            + concentration
            + cash_allocation
            + spread
        )
    )

    strengths = []
    improvements = []

    if diversification >= 24:
        strengths.append("Good spread across individual holdings.")
    else:
        improvements.append(
            "Portfolio diversification could be broader."
        )

    if concentration >= 20:
        strengths.append(
            "Top holdings are reasonably balanced."
        )
    else:
        improvements.append(
            "A large portion of the portfolio is concentrated "
            "in the biggest holdings."
        )

    if cash_allocation >= 16:
        strengths.append(
            "Cash percentage falls within the score model's middle band."
        )
    else:
        improvements.append(
            "The cash percentage falls outside the score model's middle band."
        )

    if spread >= 20:
        strengths.append(
            "Portfolio concentration risk is relatively low."
        )
    else:
        improvements.append(
            "The portfolio may be sensitive to a small number "
            "of positions."
        )

    return {
        "score": total_score,
        "grade": score_to_grade(total_score),
        "label": score_to_label(total_score),
        "categories": [
            {
                "name": "Diversification",
                "score": diversification,
                "maximum": 30,
            },
            {
                "name": "Concentration",
                "score": concentration,
                "maximum": 25,
            },
            {
                "name": "Cash Allocation",
                "score": cash_allocation,
                "maximum": 20,
            },
            {
                "name": "Portfolio Spread",
                "score": spread,
                "maximum": 25,
            },
        ],
        "strengths": strengths,
        "improvements": improvements,
    }