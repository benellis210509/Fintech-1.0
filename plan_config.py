"""Single source of truth for subscription entitlements."""

PLAN_CONFIG = {
    "free": {
        "label": "Free",
        "monthly_analyses": 1,
        "watchlist_limit": 5,
        "advanced_reports": False,
    },
    "pro": {
        "label": "Pro",
        "monthly_analyses": 5,
        "watchlist_limit": None,
        "advanced_reports": True,
    },
    "premium": {
        "label": "Premium",
        "monthly_analyses": 20,
        "watchlist_limit": None,
        "advanced_reports": True,
    },
    "admin": {
        "label": "Admin",
        "monthly_analyses": None,
        "watchlist_limit": None,
        "advanced_reports": True,
    },
}


def normalize_plan(plan):
    value = str(plan or "free").strip().lower()
    return value if value in PLAN_CONFIG else "free"


def plan_details(plan):
    name = normalize_plan(plan)
    return name, PLAN_CONFIG[name]


def monthly_analysis_limit(plan):
    _, details = plan_details(plan)
    return details["monthly_analyses"]


def watchlist_limit(plan):
    _, details = plan_details(plan)
    return details["watchlist_limit"]


def has_advanced_reports(plan):
    _, details = plan_details(plan)
    return bool(details["advanced_reports"])


def is_paid_plan(plan):
    return normalize_plan(plan) in ("pro", "premium")
