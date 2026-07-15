from plan_config import (
    has_advanced_reports,
    monthly_analysis_limit,
    normalize_plan,
    watchlist_limit,
)


def test_plan_entitlements_are_consistent():
    assert normalize_plan("unknown") == "free"
    assert monthly_analysis_limit("free") == 1
    assert monthly_analysis_limit("pro") == 5
    assert monthly_analysis_limit("premium") == 20
    assert watchlist_limit("free") == 5
    assert watchlist_limit("pro") is None
    assert has_advanced_reports("pro") is True
    assert has_advanced_reports("premium") is True
    assert has_advanced_reports("free") is False
