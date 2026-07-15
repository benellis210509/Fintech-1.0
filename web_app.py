from pathlib import Path
import csv
import os
import shutil
import sqlite3
import traceback
import secrets
import re

import stripe
from stripe import SignatureVerificationError
import yahoo_data
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from portfolio_score import calculate_portfolio_score
from datetime import datetime

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()

from config import (
    APP_NAME, BASE_DIR, DATA_DIR, REPORTS_DIR, CHARTS_DIR, MAX_UPLOAD_BYTES,
    MAX_CSV_ROWS, TERMS_VERSION, LEGAL_ENTITY_NAME, SUPPORT_EMAIL, PRIVACY_EMAIL,
    PAID_PLANS_ENABLED, ensure_directories,
)
from database import (
    claim_stripe_event, cleanup_failed_analysis, complete_portfolio_analysis,
    complete_stripe_event, create_tables, create_user, fail_portfolio_analysis,
    fail_stripe_event,
    get_admin_stats, get_connection, get_monthly_analysis_usage, get_setting,
    get_user_by_email, get_user_by_id, get_user_by_stripe_customer,
    get_user_report, get_user_subscription, hash_password, list_user_reports,
    list_users_with_stats,
    login_attempt_is_limited, record_login_failure, reserve_portfolio_analysis,
    set_setting, update_last_login, update_user_billing, verify_password,
    clear_login_failures,
)
from plan_config import has_advanced_reports, is_paid_plan, watchlist_limit
from main import run_pipeline
from csv_importer import (
    TICKER_FIELDS, SHARES_FIELDS, PRICE_FIELDS, VALUE_FIELDS, COST_FIELDS
)

ensure_directories()
create_tables()

app = FastAPI(title="Fintech")
IS_PRODUCTION = os.environ.get("RENDER", "").lower() == "true" or os.environ.get("ENVIRONMENT", "").lower() == "production"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if IS_PRODUCTION and len(SESSION_SECRET) < 32:
    raise RuntimeError("SESSION_SECRET must be a random value of at least 32 characters in production.")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(32)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=IS_PRODUCTION,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

REQUIRED_COLUMNS = ["Ticker", "Company", "Shares", "Price", "Value", "CostBasis"]

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.environ.get("STRIPE_PRO_PRICE_ID", "")
STRIPE_PREMIUM_PRICE_ID = os.environ.get("STRIPE_PREMIUM_PRICE_ID", "")
stripe.api_key = STRIPE_SECRET_KEY

PLAN_PRICE_IDS = {
    "pro": STRIPE_PRO_PRICE_ID,
    "premium": STRIPE_PREMIUM_PRICE_ID,
}

LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 5


def login_key(request, email):
    host = request.client.host if request.client else "unknown"
    return "{}:{}".format(host, email.strip().lower())


def login_is_limited(request, email):
    return login_attempt_is_limited(
        login_key(request, email), LOGIN_WINDOW_SECONDS, LOGIN_MAX_ATTEMPTS
    )


def record_failed_login(request, email):
    record_login_failure(login_key(request, email))


def clear_failed_logins(request, email):
    clear_login_failures(login_key(request, email))


def current_user(request):
    user_id = request.session.get("user_id")
    return get_user_by_id(user_id) if user_id else None


def login_redirect(request):
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    return None


def is_admin_user(user):
    if not user:
        return False
    return bool(user["is_admin"])


def absolute_url(request, path):
    return str(request.base_url).rstrip("/") + path


def plan_from_price_id(price_id):
    for plan_name, configured_price_id in PLAN_PRICE_IDS.items():
        if configured_price_id and configured_price_id == price_id:
            return plan_name
    return "free"


def get_settings(user_id):
    return {
        "benchmark": get_setting("benchmark", "S&P 500", user_id=user_id),
        "risk_profile": get_setting("risk_profile", "Moderate", user_id=user_id),
        "report_type": get_setting("report_type", "Full Report", user_id=user_id),
    }


def get_csrf_token(request):
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def valid_csrf(request, submitted):
    expected = request.session.get("csrf_token", "")
    return bool(expected and submitted and secrets.compare_digest(expected, submitted))


def csrf_error():
    return Response("The form expired or could not be verified. Refresh the page and try again.", status_code=403)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self' https://checkout.stripe.com https://billing.stripe.com"
    )
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def page_context(request, **extra):
    user = current_user(request)

    settings = (
        get_settings(user["id"])
        if user
        else {
            "benchmark": "S&P 500",
            "risk_profile": "Moderate",
            "report_type": "Full Report",
        }
    )

    subscription = (
        get_user_subscription(user["id"])
        if user
        else {
            "plan": "free",
            "limit": 1,
        }
    )

    analyses_used = (
        get_monthly_analysis_usage(user["id"])
        if user
        else 0
    )

    analysis_limit = int(subscription.get("limit") or 1)
    analyses_remaining = max(analysis_limit - analyses_used, 0)

    if user:
        user = dict(user)
        user["plan"] = subscription["plan"]
        user["subscription_plan"] = subscription["plan"]
        user["monthly_analysis_limit"] = analysis_limit

    context = {
        "request": request,
        "user": user,
        "settings": settings,
        "subscription": subscription,
        "analyses_used": analyses_used,
        "analysis_limit": analysis_limit,
        "analyses_remaining": analyses_remaining,
        "csrf_token": get_csrf_token(request),
        "app_name": APP_NAME,
        "legal_entity_name": LEGAL_ENTITY_NAME,
        "support_email": SUPPORT_EMAIL,
        "privacy_email": PRIVACY_EMAIL,
        "terms_version": TERMS_VERSION,
    }

    context.update(extra)
    return context


def validate_csv(path):
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            columns = [str(column or "").strip().lower() for column in (reader.fieldnames or [])]
            if not columns:
                return False, "The CSV has no header row."

            def has_any(names):
                return any(name.lower() in columns for name in names)

            if not has_any(TICKER_FIELDS):
                return False, "A ticker or symbol column is required."
            has_value = has_any(VALUE_FIELDS)
            has_quantity_and_price = has_any(SHARES_FIELDS) and has_any(PRICE_FIELDS)
            if not has_value and not has_quantity_and_price:
                return False, "Include a market value column, or both shares and price columns."

            row_count = sum(1 for _ in reader)
            if row_count == 0:
                return False, "CSV has no data rows."
            if row_count > MAX_CSV_ROWS:
                return False, "CSV exceeds the maximum of {} rows.".format(MAX_CSV_ROWS)
        return True, "CSV is valid."
    except (OSError, UnicodeError, csv.Error):
        traceback.print_exc()
        return False, "The CSV could not be read. Check that it is a normal UTF-8 CSV file."


def money(value, currency="NZD"):
    try:
        return "{} {:,.2f}".format(str(currency or "NZD").upper(), float(value or 0))
    except Exception:
        return "{} 0.00".format(str(currency or "NZD").upper())


def percent(value):
    try:
        return "{:+.2f}%".format(float(value or 0))
    except Exception:
        return "+0.00%"


def get_latest_dashboard(user_id):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                snapshot_date,
                total_value,
                cash_balance,
                base_currency
            FROM portfolio_snapshots
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,))

        snapshot = cursor.fetchone()

        if not snapshot:
            return None

        snapshot_id = snapshot["id"]
        equity = float(snapshot["total_value"] or 0)
        cash = float(snapshot["cash_balance"] or 0)
        total = equity + cash
        base_currency = snapshot["base_currency"] or "NZD"

        cursor.execute("""
            SELECT
                ticker,
                company_name,
                market_value
            FROM holdings
            WHERE snapshot_id = ?
            ORDER BY market_value DESC
        """, (snapshot_id,))

        holdings = cursor.fetchall()

        cursor.execute("""
            SELECT
                total_value,
                cash_balance
            FROM portfolio_snapshots
            WHERE user_id = ?
              AND id < ?
            ORDER BY id DESC
            LIMIT 1
        """, (user_id, snapshot_id))

        previous = cursor.fetchone()

        change = 0.0
        change_pct = 0.0

        if previous:
            previous_total = (
                float(previous["total_value"] or 0)
                + float(previous["cash_balance"] or 0)
            )

            change = total - previous_total

            if previous_total:
                change_pct = change / previous_total * 100

        allocation = []
        hhi = 0.0

        for row in holdings:
            value = float(row["market_value"] or 0)
            weight = value / total if total else 0

            hhi += weight ** 2

            allocation.append({
                "ticker": row["ticker"],
                "weight": round(weight * 100, 1),
                "value": money(value, base_currency),
            })

        if total:
            hhi += (cash / total) ** 2

        largest_weight = (
            float(holdings[0]["market_value"] or 0)
            / total
            * 100
            if holdings and total
            else 0
        )

        cash_pct_number = (
            cash / total * 100
            if total
            else 0
        )

        portfolio_score = calculate_portfolio_score(
            holdings_count=len(holdings),
            cash_pct=cash_pct_number,
            largest_weight=largest_weight,
            allocation=allocation,
        )

        return {
            "snapshot_date": snapshot["snapshot_date"],
            "portfolio_value": money(total, base_currency),
            "cash_balance": money(cash, base_currency),
            "holdings_count": len(holdings),
            "cash_pct": "{:.1f}%".format(cash_pct_number),
            "monthly_change": money(change, base_currency),
            "monthly_change_pct": percent(change_pct),
            "diversification_score": int((1 - min(hhi, 1)) * 100),
            "base_currency": base_currency,
            "largest_holding": (
                holdings[0]["ticker"]
                if holdings
                else "N/A"
            ),
            "largest_weight": "{:.1f}%".format(
                largest_weight
            ),
            "allocation_chart": allocation[:8],
            "portfolio_score": portfolio_score,
        }

    finally:
        conn.close()


def report_files(user_id):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        REPORTS_DIR.glob("user_{}_*.pdf".format(user_id)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def get_watchlist(user_id):
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ticker, company_name, notes, created_at FROM watchlist
            WHERE user_id = ? ORDER BY ticker
        """, (user_id,)).fetchall()
    finally:
        conn.close()
    items = []
    for row in rows:
        item = dict(row)
        try:
            data = yahoo_data.fetch_ticker_data(item["ticker"]) or {}
            price = data.get("price")
            item["price"] = "{} {:,.2f}".format(data.get("currency") or "", float(price)).strip() if price else "Unavailable"
            item["sector"] = data.get("sector") or "Unknown Sector"
        except Exception:
            item["price"] = "Unavailable"
            item["sector"] = "Unknown Sector"
        items.append(item)
    return items


@app.head("/")
def health_check():
    return Response(status_code=200)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/signup")
def signup_page(request: Request):
    if current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="signup.html", context=page_context(request, error=None))


@app.post("/signup")
def signup(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), accept_terms: str = Form(""), csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return csrf_error()
    error = None
    if accept_terms != "yes":
        error = "You must accept the Terms and acknowledge the Privacy Policy."
    elif len(name.strip()) < 2:
        error = "Please enter your name."
    elif len(name.strip()) > 100:
        error = "Name is too long."
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        error = "Please enter a valid email address."
    elif len(email.strip()) > 254:
        error = "Email address is too long."
    elif len(password) < 10:
        error = "Password must be at least 10 characters."
    elif len(password) > 200:
        error = "Password is too long."
    elif password != confirm_password:
        error = "Passwords do not match."
    if error:
        return templates.TemplateResponse(request=request, name="signup.html", context=page_context(request, error=error))
    try:
        user_id = create_user(name, email, password, terms_version=TERMS_VERSION)
        if ADMIN_EMAIL and email.strip().lower() == ADMIN_EMAIL:
            conn = get_connection()
            try:
                conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
                conn.commit()
            finally:
                conn.close()
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(request=request, name="signup.html", context=page_context(request, error="An account with that email already exists."))
    request.session.clear()
    request.session["user_id"] = user_id
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login")
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context=page_context(request, error=None))


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
):
    if not valid_csrf(request, csrf_token):
        return csrf_error()

    if login_is_limited(request, email):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=page_context(
                request,
                error="Too many login attempts. Wait 15 minutes and try again.",
            ),
            status_code=429,
        )

    user = get_user_by_email(email)

    if not user or not verify_password(password, user["password_hash"]):
        record_failed_login(request, email)

        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=page_context(
                request,
                error="Incorrect email or password.",
            ),
        )

    clear_failed_logins(request, email)

    if ADMIN_EMAIL and user["email"].strip().lower() == ADMIN_EMAIL:
        conn = get_connection()

        try:
            conn.execute(
                "UPDATE users SET is_admin = 1 WHERE id = ?",
                (user["id"],),
            )
            conn.commit()
        finally:
            conn.close()

    request.session.clear()
    request.session["user_id"] = user["id"]
    update_last_login(user["id"])

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/logout")
def logout(request: Request, csrf_token: str = Form("")):
    if not valid_csrf(request, csrf_token):
        return csrf_error()
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context=page_context(
            request,
            stripe_ready=bool(STRIPE_SECRET_KEY and STRIPE_PRO_PRICE_ID),
            paid_plans_enabled=PAID_PLANS_ENABLED,
        ),
    )


@app.get("/privacy")
def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context=page_context(request))


@app.get("/terms")
def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html", context=page_context(request))


@app.get("/disclaimer")
def disclaimer_page(request: Request):
    return templates.TemplateResponse(request=request, name="disclaimer.html", context=page_context(request))


@app.get("/dashboard")
def dashboard_page(request: Request):
    redirect = login_redirect(request)
    if redirect: return redirect
    user = current_user(request)
    return templates.TemplateResponse(request=request, name="dashboard.html", context=page_context(request, dashboard=get_latest_dashboard(user["id"])))


@app.get("/upload")
def upload_page(request: Request):
    redirect = login_redirect(request)
    if redirect: return redirect
    return templates.TemplateResponse(request=request, name="upload.html", context=page_context(request, message=None, report_path=None))


@app.post("/upload")
def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()

    user = current_user(request)
    upload_id = secrets.token_hex(12)
    temp_path = DATA_DIR / "user_{}_{}_temp.csv".format(user["id"], upload_id)
    csv_path = DATA_DIR / "user_{}_{}.csv".format(user["id"], upload_id)
    reservation_token = None
    previous_snapshot_id = None
    analysis_started = False

    try:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            return templates.TemplateResponse(
                request=request,
                name="upload.html",
                context=page_context(
                    request,
                    message="Please select a valid CSV file.",
                    report_path=None,
                ),
                status_code=400,
            )

        total_bytes = 0
        with open(temp_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise ValueError(
                        "The CSV file is too large. Maximum size is {:.1f} MB.".format(
                            MAX_UPLOAD_BYTES / 1024 / 1024
                        )
                    )
                buffer.write(chunk)

        valid, validation_message = validate_csv(temp_path)
        if not valid:
            return templates.TemplateResponse(
                request=request,
                name="upload.html",
                context=page_context(
                    request,
                    message="CSV error: " + validation_message,
                    report_path=None,
                ),
                status_code=400,
            )

        report_type = get_settings(user["id"]).get("report_type", "Full Report")
        reservation_token, reservation_error = reserve_portfolio_analysis(
            user["id"], report_type
        )
        if not reservation_token:
            status_code = 409 if "already processing" in reservation_error.lower() else 403
            return templates.TemplateResponse(
                request=request,
                name="upload.html",
                context=page_context(
                    request, message=reservation_error, report_path=None
                ),
                status_code=status_code,
            )

        shutil.move(str(temp_path), str(csv_path))

        conn = get_connection()
        try:
            previous_snapshot = conn.execute(
                "SELECT id FROM portfolio_snapshots WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user["id"],),
            ).fetchone()
            previous_snapshot_id = previous_snapshot["id"] if previous_snapshot else None
        finally:
            conn.close()

        analysis_started = True
        report_path = run_pipeline(user_id=user["id"], csv_path=csv_path)

        conn = get_connection()
        try:
            latest_snapshot = conn.execute(
                """
                SELECT id FROM portfolio_snapshots
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (user["id"],),
            ).fetchone()
        finally:
            conn.close()

        if not latest_snapshot:
            raise RuntimeError("The analysis completed without creating a portfolio snapshot.")

        complete_portfolio_analysis(reservation_token, latest_snapshot["id"])
        reservation_token = None

        subscription = get_user_subscription(user["id"])
        used_now = get_monthly_analysis_usage(user["id"])
        analysis_limit = int(subscription.get("limit") or 1)
        remaining = max(analysis_limit - used_now, 0)

        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context=page_context(
                request,
                message=(
                    "Portfolio analysed successfully. "
                    "{} analysis{} remaining this month."
                ).format(remaining, "" if remaining == 1 else "es"),
                report_path=report_path,
            ),
        )

    except ValueError as exc:
        if analysis_started:
            cleanup = cleanup_failed_analysis(user["id"], previous_snapshot_id)
            for report_file in cleanup["report_paths"]:
                Path(report_file).unlink(missing_ok=True)
            for snapshot_id in cleanup["snapshot_ids"]:
                for chart in CHARTS_DIR.glob("*_{}.png".format(snapshot_id)):
                    chart.unlink(missing_ok=True)
        fail_portfolio_analysis(reservation_token, exc)
        reservation_token = None
        message = str(exc) or "The uploaded CSV is not valid."
        status_code = 413 if "too large" in message.lower() else 400
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context=page_context(request, message=message, report_path=None),
            status_code=status_code,
        )

    except Exception as exc:
        if analysis_started:
            try:
                cleanup = cleanup_failed_analysis(user["id"], previous_snapshot_id)
                for report_file in cleanup["report_paths"]:
                    Path(report_file).unlink(missing_ok=True)
                for snapshot_id in cleanup["snapshot_ids"]:
                    for chart in CHARTS_DIR.glob("*_{}.png".format(snapshot_id)):
                        chart.unlink(missing_ok=True)
            except Exception:
                traceback.print_exc()
        fail_portfolio_analysis(reservation_token, exc)
        reservation_token = None
        traceback.print_exc()
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context=page_context(
                request,
                message=(
                    "The analysis could not be completed. No monthly allowance "
                    "was charged. Check the CSV and try again."
                ),
                report_path=None,
            ),
            status_code=500,
        )

    finally:
        temp_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)
        file.file.close()


def resolved_report_path(report_row, user_id):
    if not report_row:
        return None
    try:
        path = Path(report_row["report_path"]).expanduser().resolve()
        reports_root = REPORTS_DIR.resolve()
        if path.parent != reports_root:
            return None
        if not path.name.startswith("user_{}_".format(user_id)):
            return None
        if path.suffix.lower() != ".pdf" or not path.is_file():
            return None
        return path
    except (OSError, RuntimeError, TypeError):
        return None


@app.get("/reports")
def reports_page(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    user_id = current_user(request)["id"]
    reports = []
    for row in list_user_reports(user_id, limit=20):
        path = resolved_report_path(row, user_id)
        if path:
            reports.append({
                "id": row["id"],
                "name": path.name,
                "size_kb": round(path.stat().st_size / 1024, 1),
                "created_at": row["created_at"],
            })
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context=page_context(request, reports=reports),
    )


@app.get("/download")
def download_report(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    user_id = current_user(request)["id"]
    rows = list_user_reports(user_id, limit=1)
    path = resolved_report_path(rows[0], user_id) if rows else None
    if not path:
        return Response("No report found.", status_code=404)
    return FileResponse(path=str(path), filename=path.name, media_type="application/pdf")


@app.get("/reports/{report_id}/download")
def download_report_by_id(request: Request, report_id: int):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    user_id = current_user(request)["id"]
    path = resolved_report_path(get_user_report(report_id, user_id), user_id)
    if not path:
        return Response("Not found", status_code=404)
    return FileResponse(path=str(path), filename=path.name, media_type="application/pdf")


@app.get("/download/{filename}")
def download_specific_report(request: Request, filename: str):
    """Legacy filename route retained for old bookmarks, with strict ownership checks."""
    redirect = login_redirect(request)
    if redirect:
        return redirect
    user_id = current_user(request)["id"]
    safe_name = Path(filename).name
    if not safe_name.startswith("user_{}_".format(user_id)):
        return Response("Not found", status_code=404)
    path = (REPORTS_DIR / safe_name).resolve()
    if path.parent != REPORTS_DIR.resolve() or not path.exists() or path.suffix.lower() != ".pdf":
        return Response("Not found", status_code=404)
    return FileResponse(path=str(path), filename=path.name, media_type="application/pdf")


@app.get("/watchlist")
def watchlist_page(request: Request):
    redirect = login_redirect(request)
    if redirect: return redirect
    user = current_user(request)
    return templates.TemplateResponse(request=request, name="watchlist.html", context=page_context(request, watchlist=get_watchlist(user["id"]), message=None))


@app.post("/watchlist/add")
def add_watchlist(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    notes: str = Form(""),
    csrf_token: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    if not valid_csrf(request, csrf_token):
        return csrf_error()

    user = current_user(request)
    subscription = get_user_subscription(user["id"])
    plan = subscription.get("plan", "free")
    saved_watchlist_limit = watchlist_limit(plan)

    conn = get_connection()

    try:
        current_count = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM watchlist
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()["total"]

        if (
            not user["is_admin"]
            and saved_watchlist_limit is not None
            and int(current_count or 0) >= int(saved_watchlist_limit)
        ):
            message = (
                "Your plan can save up to {} watchlist stocks. "
                "Upgrade for an unlimited watchlist."
            ).format(saved_watchlist_limit)

            return templates.TemplateResponse(
                request=request,
                name="watchlist.html",
                context=page_context(
                    request,
                    watchlist=get_watchlist(user["id"]),
                    message=message,
                    success=False,
                ),
                status_code=403,
            )

    finally:
        conn.close()

    ticker = ticker.strip().upper()
    company_name = company_name.strip()
    notes = notes.strip()
    if not re.fullmatch(r"[A-Z0-9.\-^=]{1,20}", ticker):
        return templates.TemplateResponse(
            request=request,
            name="watchlist.html",
            context=page_context(
                request,
                watchlist=get_watchlist(user["id"]),
                message="Enter a valid ticker containing no more than 20 characters.",
                success=False,
            ),
            status_code=400,
        )
    if len(company_name) > 150 or len(notes) > 3000:
        return templates.TemplateResponse(
            request=request,
            name="watchlist.html",
            context=page_context(
                request,
                watchlist=get_watchlist(user["id"]),
                message="Company names are limited to 150 characters and notes to 3,000.",
                success=False,
            ),
            status_code=400,
        )
    message = ticker + " added to watchlist."
    success = True

    try:
        data = yahoo_data.fetch_ticker_data(ticker) or {}

        if not data.get("price"):
            raise ValueError("Ticker does not look valid.")

        conn = get_connection()

        try:
            conn.execute(
                """
                INSERT INTO watchlist (
                    user_id,
                    ticker,
                    company_name,
                    notes
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user["id"],
                    ticker,
                    company_name,
                    notes,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    except sqlite3.IntegrityError:
        success = False
        message = ticker + " is already in your watchlist."

    except Exception:
        traceback.print_exc()
        success = False
        message = (
            "The ticker could not be added. "
            "Market data may be unavailable or delayed."
        )

    return templates.TemplateResponse(
        request=request,
        name="watchlist.html",
        context=page_context(
            request,
            watchlist=get_watchlist(user["id"]),
            message=message,
            success=success,
        ),
    )


@app.post("/watchlist/edit")
def edit_watchlist(
    request: Request,
    ticker: str = Form(...),
    company_name: str = Form(""),
    notes: str = Form(""),
    csrf_token: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()

    ticker = ticker.strip().upper()
    company_name = company_name.strip()
    notes = notes.strip()
    if not re.fullmatch(r"[A-Z0-9.\-^=]{1,20}", ticker):
        return RedirectResponse(
            "/watchlist?toast=Invalid+ticker", status_code=303
        )
    if len(company_name) > 150 or len(notes) > 3000:
        return RedirectResponse(
            "/watchlist?toast=Notes+or+company+name+are+too+long",
            status_code=303,
        )

    user = current_user(request)
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE watchlist SET company_name = ?, notes = ?
            WHERE user_id = ? AND ticker = ?
            """,
            (company_name, notes, user["id"], ticker),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse("/watchlist?toast=Changes+saved", status_code=303)


@app.post("/watchlist/delete")
def delete_watchlist(
    request: Request, ticker: str = Form(...), csrf_token: str = Form("")
):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()
    user = current_user(request)
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user["id"], ticker.strip().upper()),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse("/watchlist?toast=Stock+removed", status_code=303)


@app.get("/account")
def account_page(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    user = current_user(request)
    subscription = get_user_subscription(user["id"])
    analyses_used = get_monthly_analysis_usage(user["id"])
    analysis_limit = int(subscription.get("limit") or 1)
    analyses_remaining = max(analysis_limit - analyses_used, 0)

    next_billing_date = None
    cancel_at_period_end = False

    if (
        is_paid_plan(subscription.get("plan"))
        and STRIPE_SECRET_KEY
        and user["stripe_subscription_id"]
    ):
        try:
            stripe_subscription = stripe.Subscription.retrieve(
                user["stripe_subscription_id"]
            )

            current_period_end = stripe_subscription.get(
                "current_period_end"
            )

            if current_period_end:
                next_billing_date = datetime.fromtimestamp(
                    current_period_end
                ).strftime("%d %B %Y")

            cancel_at_period_end = bool(
                stripe_subscription.get(
                    "cancel_at_period_end",
                    False,
                )
            )

        except Exception:
            traceback.print_exc()

    return templates.TemplateResponse(
        request=request,
        name="account.html",
        context=page_context(
            request,
            account_subscription=subscription,
            analyses_used=analyses_used,
            analysis_limit=analysis_limit,
            analyses_remaining=analyses_remaining,
            next_billing_date=next_billing_date,
            cancel_at_period_end=cancel_at_period_end,
        ),
    )


@app.post("/account/password")
def update_account_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    if not valid_csrf(request, csrf_token):
        return csrf_error()

    user = current_user(request)

    if not verify_password(
        current_password,
        user["password_hash"],
    ):
        return RedirectResponse(
            "/account?toast=Current+password+is+incorrect",
            status_code=303,
        )

    if len(new_password) < 10:
        return RedirectResponse(
            "/account?toast=New+password+must+contain+at+least+10+characters",
            status_code=303,
        )

    if new_password != confirm_password:
        return RedirectResponse(
            "/account?toast=New+passwords+do+not+match",
            status_code=303,
        )

    if verify_password(
        new_password,
        user["password_hash"],
    ):
        return RedirectResponse(
            "/account?toast=Choose+a+different+password",
            status_code=303,
        )

    conn = get_connection()

    try:
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (
                hash_password(new_password),
                user["id"],
            ),
        )

        conn.commit()

    finally:
        conn.close()

    return RedirectResponse(
        "/account?toast=Password+updated+successfully",
        status_code=303,
    )


@app.get("/settings")
def settings_page(request: Request):
    redirect = login_redirect(request)
    if redirect: return redirect
    return templates.TemplateResponse(request=request, name="settings.html", context=page_context(request))


@app.post("/settings")
def save_settings(
    request: Request,
    benchmark: str = Form(...),
    risk_profile: str = Form(...),
    report_type: str = Form(...),
    csrf_token: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()

    allowed_benchmarks = {"S&P 500", "NASDAQ 100", "NZX 50"}
    allowed_risk_profiles = {"Conservative", "Moderate", "Aggressive"}
    allowed_report_types = {"Quick Summary", "Full Report", "Deep Analysis"}
    if (
        benchmark not in allowed_benchmarks
        or risk_profile not in allowed_risk_profiles
        or report_type not in allowed_report_types
    ):
        return RedirectResponse(
            "/settings?toast=Invalid+setting+selection", status_code=303
        )

    user = current_user(request)
    user_id = user["id"]
    plan = get_user_subscription(user_id).get("plan", "free")
    if (
        not user["is_admin"]
        and not has_advanced_reports(plan)
        and report_type == "Deep Analysis"
    ):
        return RedirectResponse(
            "/settings?toast=Deep+Analysis+requires+a+paid+plan",
            status_code=303,
        )

    for key, value in (
        ("benchmark", benchmark),
        ("risk_profile", risk_profile),
        ("report_type", report_type),
    ):
        set_setting(key, value, user_id=user_id)

    return RedirectResponse(
        "/settings?toast=Preferences+saved", status_code=303
    )


@app.get("/admin")
def admin_page(request: Request):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    user = current_user(request)
    if not is_admin_user(user):
        return Response("Forbidden", status_code=403)
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context=page_context(
            request,
            users=list_users_with_stats(),
            admin_stats=get_admin_stats(),
        ),
    )


@app.post("/create-checkout-session/{plan_name}")
def create_checkout_session(
    request: Request,
    plan_name: str,
    csrf_token: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()
    if not PAID_PLANS_ENABLED:
        return Response("Paid plans are not enabled yet.", status_code=503)

    user = current_user(request)
    plan_name = plan_name.strip().lower()
    price_id = PLAN_PRICE_IDS.get(plan_name)
    if not STRIPE_SECRET_KEY or not price_id:
        return Response("Payments are not configured yet.", status_code=503)

    try:
        customer_id = user["stripe_customer_id"]
        if not customer_id:
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["name"],
                metadata={"user_id": str(user["id"])},
            )
            customer_id = customer.id
            update_user_billing(user["id"], stripe_customer_id=customer_id)

        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=absolute_url(
                request, "/billing/success?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=absolute_url(request, "/#pricing"),
            client_reference_id=str(user["id"]),
            metadata={"user_id": str(user["id"]), "plan": plan_name},
            subscription_data={
                "metadata": {"user_id": str(user["id"]), "plan": plan_name}
            },
            allow_promotion_codes=True,
        )
        return RedirectResponse(checkout.url, status_code=303)
    except Exception:
        traceback.print_exc()
        return Response(
            "Checkout could not be started. Please try again later.", status_code=500
        )


@app.get("/billing/success")
def billing_success(request: Request, session_id: str = ""):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    message = (
        "Stripe is confirming the subscription. Access changes are applied only after "
        "a verified Stripe webhook is received."
    )
    if STRIPE_SECRET_KEY and session_id:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            expected_user = str(current_user(request)["id"])
            if str(checkout.client_reference_id or "") != expected_user:
                return Response("Not found", status_code=404)
            if checkout.payment_status in ("paid", "no_payment_required"):
                message = "Payment was received. The verified webhook will confirm the plan shortly."
        except Exception:
            traceback.print_exc()

    return templates.TemplateResponse(
        request=request,
        name="billing_success.html",
        context=page_context(request, message=message),
    )


@app.post("/billing/portal")
def billing_portal(request: Request, csrf_token: str = Form("")):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()

    user = current_user(request)
    if not STRIPE_SECRET_KEY or not user["stripe_customer_id"]:
        return RedirectResponse("/#pricing", status_code=303)
    try:
        portal = stripe.billing_portal.Session.create(
            customer=user["stripe_customer_id"],
            return_url=absolute_url(request, "/account"),
        )
        return RedirectResponse(portal.url, status_code=303)
    except Exception:
        traceback.print_exc()
        return Response(
            "The billing portal could not be opened. Please try again later.",
            status_code=500,
        )


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_WEBHOOK_SECRET:
        return Response("Webhook secret not configured", status_code=503)

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return Response("Invalid payload", status_code=400)
    except SignatureVerificationError:
        return Response("Invalid signature", status_code=400)

    event_id = event.get("id")
    event_type = event.get("type", "unknown")
    if not claim_stripe_event(event_id, event_type):
        return {"received": True, "duplicate": True}

    try:
        obj = event["data"]["object"]

        if event_type == "checkout.session.completed":
            metadata = obj.get("metadata") or {}
            user_id = metadata.get("user_id") or obj.get("client_reference_id")
            if user_id:
                update_user_billing(
                    int(user_id),
                    stripe_customer_id=obj.get("customer"),
                    stripe_subscription_id=obj.get("subscription"),
                    subscription_status="processing",
                )

        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "customer.subscription.paused",
            "customer.subscription.resumed",
        ):
            customer_id = obj.get("customer")
            user = get_user_by_stripe_customer(customer_id) if customer_id else None
            metadata = obj.get("metadata") or {}
            user_id = metadata.get("user_id") or (user["id"] if user else None)
            if user_id:
                items = obj.get("items", {}).get("data", [])
                price_id = (items[0].get("price") or {}).get("id", "") if items else ""
                status = obj.get("status", "inactive")
                if status in ("active", "trialing"):
                    plan_name = metadata.get("plan") or plan_from_price_id(price_id)
                else:
                    plan_name = "free"
                update_user_billing(
                    int(user_id),
                    plan=plan_name,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=obj.get("id"),
                    subscription_status=status,
                )

        elif event_type in ("invoice.payment_failed", "invoice.marked_uncollectible"):
            customer_id = obj.get("customer")
            user = get_user_by_stripe_customer(customer_id) if customer_id else None
            if user:
                update_user_billing(
                    user["id"], plan="free", subscription_status="past_due"
                )

        complete_stripe_event(event_id)
        return {"received": True}

    except Exception as exc:
        fail_stripe_event(event_id, exc)
        traceback.print_exc()
        return Response("Webhook processing failed", status_code=500)


@app.post("/settings/reset-data")
def reset_data(request: Request, csrf_token: str = Form("")):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    if not valid_csrf(request, csrf_token):
        return csrf_error()

    user_id = current_user(request)["id"]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        snapshot_ids = [
            row["id"]
            for row in cursor.execute(
                "SELECT id FROM portfolio_snapshots WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
        cursor.execute("DELETE FROM recommendations WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM report_runs WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM portfolio_snapshots WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    for report in report_files(user_id):
        report.unlink(missing_ok=True)
    for data_file in DATA_DIR.glob("user_{}_*.csv".format(user_id)):
        data_file.unlink(missing_ok=True)
    for snapshot_id in snapshot_ids:
        for chart in CHARTS_DIR.glob("*_{}.png".format(snapshot_id)):
            chart.unlink(missing_ok=True)

    return RedirectResponse("/settings?reset=success&toast=Portfolio+data+reset", status_code=303)
