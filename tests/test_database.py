import importlib
import sys


def load_database(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "portfolio.db"))
    monkeypatch.setenv("APP_TIMEZONE", "Pacific/Auckland")
    for module in ("config", "database"):
        sys.modules.pop(module, None)
    import config
    import database
    importlib.reload(config)
    importlib.reload(database)
    database.create_tables()
    return database


def test_failed_analysis_does_not_use_allowance(tmp_path, monkeypatch):
    database = load_database(tmp_path, monkeypatch)
    user_id = database.create_user("Test User", "test@example.com", "password1234")

    token, error = database.reserve_portfolio_analysis(user_id, "Full Report")
    assert token and error is None
    assert database.get_monthly_analysis_usage(user_id) == 1

    second_token, second_error = database.reserve_portfolio_analysis(
        user_id, "Full Report"
    )
    assert second_token is None
    assert "already processing" in second_error.lower()

    database.fail_portfolio_analysis(token, "simulated failure")
    assert database.get_monthly_analysis_usage(user_id) == 0


def test_stripe_failed_event_can_retry(tmp_path, monkeypatch):
    database = load_database(tmp_path, monkeypatch)
    assert database.claim_stripe_event("evt_test", "customer.subscription.updated")
    assert not database.claim_stripe_event("evt_test", "customer.subscription.updated")

    database.fail_stripe_event("evt_test", "temporary failure")
    assert database.claim_stripe_event("evt_test", "customer.subscription.updated")

    database.complete_stripe_event("evt_test")
    assert not database.claim_stripe_event("evt_test", "customer.subscription.updated")


def test_premium_plan_has_correct_limit(tmp_path, monkeypatch):
    database = load_database(tmp_path, monkeypatch)
    user_id = database.create_user("Premium User", "premium@example.com", "password1234")
    database.update_user_billing(
        user_id, plan="premium", subscription_status="active"
    )
    subscription = database.get_user_subscription(user_id)
    assert subscription == {"plan": "premium", "limit": 20}
