# risk_engine.py
from config import MAX_CASH_WEIGHT, MAX_SECTOR_WEIGHT, MAX_SINGLE_STOCK_WEIGHT, MAX_TOP5_WEIGHT, MIN_CASH_WEIGHT
from utils import safe_div


def get_risk_limits(risk_profile="Moderate"):
    if risk_profile == "Conservative":
        return {"max_single_stock": 0.20, "max_sector": 0.35, "max_top5": 0.65, "max_cash": 0.25, "min_cash": 0.05}
    if risk_profile == "Aggressive":
        return {"max_single_stock": 0.40, "max_sector": 0.55, "max_top5": 0.85, "max_cash": 0.45, "min_cash": 0.01}
    return {"max_single_stock": MAX_SINGLE_STOCK_WEIGHT, "max_sector": MAX_SECTOR_WEIGHT, "max_top5": MAX_TOP5_WEIGHT, "max_cash": MAX_CASH_WEIGHT, "min_cash": MIN_CASH_WEIGHT}


def calculate_risk(snapshot_id, analytics_summary, risk_profile="Moderate"):
    holdings = analytics_summary.get("holdings", [])
    total_value = float(analytics_summary.get("total_portfolio_value") or 0)
    cash_balance = float(analytics_summary.get("cash_balance") or 0)
    limits = get_risk_limits(risk_profile)
    warnings = []

    if total_value <= 0:
        return {"risk_score": 0, "hhi": 0.0, "max_position_weight": 0.0, "top5_weight": 0.0, "warnings": ["Portfolio value is zero or missing."], "risk_level": "Unknown", "risk_profile": risk_profile, "risk_limits": limits}

    weights = [float(h.get("weight") or 0) for h in holdings]
    cash_weight = safe_div(cash_balance, total_value)
    hhi = sum(w * w for w in weights) + cash_weight * cash_weight
    max_weight = max(weights) if weights else 0.0
    top5_weight = sum(sorted(weights, reverse=True)[:5])

    for h in holdings:
        weight = float(h.get("weight") or 0)
        if weight > limits["max_single_stock"]:
            warnings.append("High single-stock concentration: {} is {:.1f}% of the portfolio. Configured {} sensitivity threshold is {:.0f}%.".format(h.get("ticker"), weight * 100, risk_profile, limits["max_single_stock"] * 100))

    for s in analytics_summary.get("sector_weights", []):
        weight = float(s.get("weight") or 0)
        if weight > limits["max_sector"]:
            warnings.append("High sector concentration: {} is {:.1f}% of the portfolio. Configured {} sensitivity threshold is {:.0f}%.".format(s.get("sector"), weight * 100, risk_profile, limits["max_sector"] * 100))

    if top5_weight > limits["max_top5"]:
        warnings.append("Top 5 holdings make up {:.1f}% of the portfolio. Configured {} sensitivity threshold is {:.0f}%.".format(top5_weight * 100, risk_profile, limits["max_top5"] * 100))

    if cash_weight > limits["max_cash"]:
        warnings.append("Cash is {:.1f}% of the uploaded portfolio, above the configured {} sensitivity threshold of {:.0f}%.".format(cash_weight * 100, risk_profile, limits["max_cash"] * 100))
    elif cash_weight < limits["min_cash"]:
        warnings.append("Cash is {:.1f}% of the uploaded portfolio, below the configured {} sensitivity threshold of {:.0f}%.".format(cash_weight * 100, risk_profile, limits["min_cash"] * 100))

    concentration_risk = min(hhi / 0.35, 1.0) * 55
    single_name_risk = min(max_weight / limits["max_single_stock"], 2.0) * 15
    cash_risk = 10 if cash_weight > limits["max_cash"] or cash_weight < limits["min_cash"] else 0
    warning_risk = min(len(warnings) * 5, 20)
    risk_score = int(min(100, concentration_risk + single_name_risk + cash_risk + warning_risk))

    if risk_score < 30:
        risk_level = "Low"
    elif risk_score < 60:
        risk_level = "Moderate"
    elif risk_score < 80:
        risk_level = "High"
    else:
        risk_level = "Very High"

    return {"risk_score": risk_score, "risk_level": risk_level, "hhi": round(hhi, 4), "max_position_weight": round(max_weight, 4), "top5_weight": round(top5_weight, 4), "warnings": warnings, "risk_profile": risk_profile, "risk_limits": limits}
