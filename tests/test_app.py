import importlib
import re
import sys

from fastapi.testclient import TestClient


def load_app(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "portfolio.db"))
    monkeypatch.setenv(
        "SESSION_SECRET", "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
    )
    monkeypatch.setenv("PAID_PLANS_ENABLED", "false")
    modules = [
        "config", "database", "csv_importer", "analytics", "benchmark",
        "chart_engine", "main", "report_generator", "web_app",
    ]
    for module in modules:
        sys.modules.pop(module, None)
    import web_app
    importlib.reload(web_app)
    return web_app


def csrf_token(html):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match
    return match.group(1)


def signup(client, email="test@example.com"):
    token = csrf_token(client.get("/signup").text)
    response = client.post(
        "/signup",
        data={
            "name": "Test User",
            "email": email,
            "password": "password1234",
            "confirm_password": "password1234",
            "accept_terms": "yes",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_settings_and_monthly_limit(tmp_path, monkeypatch):
    web_app = load_app(tmp_path, monkeypatch)
    from csv_importer import import_csv
    from database import insert_report_run

    def fake_pipeline(user_id=None, csv_path=None):
        snapshot_id = import_csv(csv_path=csv_path, user_id=user_id)
        report_path = web_app.REPORTS_DIR / "user_{}_test.pdf".format(user_id)
        report_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        insert_report_run(report_path, snapshot_id=snapshot_id, user_id=user_id)
        return report_path

    web_app.run_pipeline = fake_pipeline
    with TestClient(web_app.app) as client:
        signup(client)
        token = csrf_token(client.get("/settings").text)
        response = client.post(
            "/settings",
            data={
                "benchmark": "NZX 50",
                "risk_profile": "Moderate",
                "report_type": "Full Report",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        csv_bytes = (
            b"Ticker,Company,Shares,Price,Value,CostBasis,Currency\n"
            b"AAPL,Apple,1,200,200,150,NZD\n"
        )
        token = csrf_token(client.get("/upload").text)
        response = client.post(
            "/upload",
            data={"csrf_token": token},
            files={"file": ("portfolio.csv", csv_bytes, "text/csv")},
        )
        assert response.status_code == 200
        assert "Portfolio analysed successfully" in response.text

        token = csrf_token(client.get("/upload").text)
        response = client.post(
            "/upload",
            data={"csrf_token": token},
            files={"file": ("portfolio.csv", csv_bytes, "text/csv")},
        )
        assert response.status_code == 403
        assert "used all" in response.text


def test_user_cannot_download_another_users_report(tmp_path, monkeypatch):
    web_app = load_app(tmp_path, monkeypatch)
    from database import create_user, insert_report_run

    with TestClient(web_app.app) as client:
        signup(client, "first@example.com")
        other_id = create_user("Other User", "other@example.com", "password1234")
        report_path = web_app.REPORTS_DIR / "user_{}_private.pdf".format(other_id)
        report_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        report_id = insert_report_run(report_path, user_id=other_id)
        response = client.get("/reports/{}/download".format(report_id))
        assert response.status_code == 404
