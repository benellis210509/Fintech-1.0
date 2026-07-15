import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE, DB_PATH, ensure_directories
from plan_config import monthly_analysis_limit, normalize_plan


def get_connection(db_path=DB_PATH):
    ensure_directories()
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    return conn


def column_exists(cursor, table_name, column_name):
    cursor.execute("PRAGMA table_info({})".format(table_name))
    return any(row["name"] == column_name for row in cursor.fetchall())


def add_column_if_missing(cursor, table_name, column_name, column_sql):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute("ALTER TABLE {} ADD COLUMN {}".format(table_name, column_sql))


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000)
    return "{}:{}".format(salt.hex(), digest.hex())


def verify_password(password, stored_hash):
    try:
        salt_hex, digest_hex = stored_hash.split(":", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 240000
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (AttributeError, TypeError, ValueError):
        return False


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT,
                subscription_plan TEXT DEFAULT 'free',
                monthly_analysis_limit INTEGER DEFAULT 1,
                is_admin INTEGER NOT NULL DEFAULT 0,
                plan TEXT NOT NULL DEFAULT 'free',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                subscription_status TEXT NOT NULL DEFAULT 'inactive',
                terms_accepted_at TEXT,
                terms_version TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                snapshot_date TEXT NOT NULL,
                cash_balance REAL NOT NULL DEFAULT 0,
                total_value REAL NOT NULL DEFAULT 0,
                source_file TEXT,
                base_currency TEXT NOT NULL DEFAULT 'NZD',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT,
                shares REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                market_value REAL NOT NULL DEFAULT 0,
                cost_basis REAL NOT NULL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                account TEXT DEFAULT '',
                sector TEXT DEFAULT 'Unknown Sector',
                FOREIGN KEY(snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                snapshot_id INTEGER,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                reasoning TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS market_cache (
                ticker TEXT PRIMARY KEY,
                last_update TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, ticker),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS report_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                snapshot_id INTEGER,
                report_path TEXT NOT NULL,
                status TEXT DEFAULT 'success',
                message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_analysis_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                snapshot_id INTEGER,
                report_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                reservation_token TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(snapshot_id) REFERENCES portfolio_snapshots(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY(user_id, key),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_key TEXT NOT NULL,
                attempted_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stripe_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                attempt_count INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                processed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Safe upgrades for databases created by earlier versions.
        add_column_if_missing(cursor, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(cursor, "users", "subscription_plan", "subscription_plan TEXT DEFAULT 'free'")
        add_column_if_missing(cursor, "users", "monthly_analysis_limit", "monthly_analysis_limit INTEGER DEFAULT 1")
        add_column_if_missing(cursor, "users", "plan", "plan TEXT NOT NULL DEFAULT 'free'")
        add_column_if_missing(cursor, "users", "stripe_customer_id", "stripe_customer_id TEXT")
        add_column_if_missing(cursor, "users", "stripe_subscription_id", "stripe_subscription_id TEXT")
        add_column_if_missing(cursor, "users", "subscription_status", "subscription_status TEXT NOT NULL DEFAULT 'inactive'")
        add_column_if_missing(cursor, "users", "terms_accepted_at", "terms_accepted_at TEXT")
        add_column_if_missing(cursor, "users", "terms_version", "terms_version TEXT")
        add_column_if_missing(cursor, "portfolio_snapshots", "user_id", "user_id INTEGER")
        add_column_if_missing(cursor, "portfolio_snapshots", "source_file", "source_file TEXT")
        add_column_if_missing(cursor, "portfolio_snapshots", "base_currency", "base_currency TEXT NOT NULL DEFAULT 'NZD'")
        add_column_if_missing(cursor, "holdings", "currency", "currency TEXT DEFAULT 'USD'")
        add_column_if_missing(cursor, "holdings", "account", "account TEXT DEFAULT ''")
        add_column_if_missing(cursor, "holdings", "sector", "sector TEXT DEFAULT 'Unknown Sector'")
        add_column_if_missing(cursor, "recommendations", "user_id", "user_id INTEGER")
        add_column_if_missing(cursor, "recommendations", "snapshot_id", "snapshot_id INTEGER")
        add_column_if_missing(cursor, "watchlist", "user_id", "user_id INTEGER")
        add_column_if_missing(cursor, "report_runs", "user_id", "user_id INTEGER")
        add_column_if_missing(cursor, "report_runs", "status", "status TEXT DEFAULT 'success'")
        add_column_if_missing(cursor, "report_runs", "message", "message TEXT")
        add_column_if_missing(cursor, "portfolio_analysis_usage", "status", "status TEXT NOT NULL DEFAULT 'completed'")
        add_column_if_missing(cursor, "portfolio_analysis_usage", "reservation_token", "reservation_token TEXT")
        add_column_if_missing(cursor, "portfolio_analysis_usage", "error_message", "error_message TEXT")
        add_column_if_missing(cursor, "portfolio_analysis_usage", "updated_at", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(cursor, "stripe_events", "status", "status TEXT NOT NULL DEFAULT 'completed'")
        add_column_if_missing(cursor, "stripe_events", "attempt_count", "attempt_count INTEGER NOT NULL DEFAULT 1")
        add_column_if_missing(cursor, "stripe_events", "error_message", "error_message TEXT")
        add_column_if_missing(cursor, "stripe_events", "created_at", "created_at TEXT DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing(cursor, "stripe_events", "updated_at", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP")

        cursor.execute("UPDATE portfolio_analysis_usage SET status = 'completed' WHERE status IS NULL OR status = ''")
        cursor.execute("UPDATE portfolio_analysis_usage SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
        cursor.execute("UPDATE stripe_events SET status = 'completed' WHERE status IS NULL OR status = ''")
        cursor.execute("UPDATE stripe_events SET updated_at = COALESCE(updated_at, processed_at, CURRENT_TIMESTAMP)")

        defaults = {
            "benchmark": "S&P 500",
            "risk_profile": "Moderate",
            "report_type": "Full Report",
        }
        for key, value in defaults.items():
            cursor.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_user ON portfolio_snapshots(user_id, id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_snapshot ON holdings(snapshot_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_user ON recommendations(user_id, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_date ON portfolio_analysis_usage(user_id, created_at, status)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_token ON portfolio_analysis_usage(reservation_token) WHERE reservation_token IS NOT NULL")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_runs_user ON report_runs(user_id, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_key ON login_attempts(attempt_key, attempted_at)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_user(name, email, password, terms_version=None):
    email = email.strip().lower()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (
                name, email, password_hash, is_admin, plan,
                subscription_plan, monthly_analysis_limit,
                terms_accepted_at, terms_version
            )
            VALUES (?, ?, ?, 0, 'free', 'free', 1, CURRENT_TIMESTAMP, ?)
            """,
            (name.strip(), email, hash_password(password), terms_version),
        )
        user_id = cursor.lastrowid
        defaults = {
            "benchmark": "S&P 500",
            "risk_profile": "Moderate",
            "report_type": "Full Report",
        }
        for key, value in defaults.items():
            cursor.execute(
                "INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?)",
                (user_id, key, value),
            )
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()


def _subscription_from_row(row):
    if not row:
        return {"plan": "free", "limit": 1}
    if row["is_admin"]:
        return {"plan": "admin", "limit": 999999}
    plan = normalize_plan(row["plan"] or row["subscription_plan"] or "free")
    limit = monthly_analysis_limit(plan)
    return {"plan": plan, "limit": int(limit if limit is not None else 999999)}


def get_user_subscription(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT plan, subscription_plan, monthly_analysis_limit, is_admin
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        return _subscription_from_row(row)
    finally:
        conn.close()


def _month_bounds_utc():
    try:
        app_tz = ZoneInfo(APP_TIMEZONE)
    except Exception:
        app_tz = timezone.utc
    now_local = datetime.now(timezone.utc).astimezone(app_tz)
    start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_local.month == 12:
        end_local = start_local.replace(year=start_local.year + 1, month=1)
    else:
        end_local = start_local.replace(month=start_local.month + 1)
    start_utc = start_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    end_utc = end_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return start_utc, end_utc


def get_monthly_analysis_usage(user_id):
    start_utc, end_utc = _month_bounds_utc()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM portfolio_analysis_usage
            WHERE user_id = ?
              AND status IN ('pending', 'completed')
              AND created_at >= ? AND created_at < ?
            """,
            (user_id, start_utc, end_utc),
        ).fetchone()
        return int(row["total"] or 0)
    finally:
        conn.close()


def reserve_portfolio_analysis(user_id, report_type):
    """Atomically reserve one monthly analysis and block duplicate concurrent jobs."""
    start_utc, end_utc = _month_bounds_utc()
    token = secrets.token_urlsafe(24)
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE portfolio_analysis_usage
            SET status = 'failed', error_message = 'Processing reservation expired',
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND status = 'pending'
              AND updated_at < datetime('now', '-2 hours')
            """,
            (user_id,),
        )
        row = conn.execute(
            """
            SELECT plan, subscription_plan, monthly_analysis_limit, is_admin
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        subscription = _subscription_from_row(row)
        pending = conn.execute(
            "SELECT COUNT(*) AS total FROM portfolio_analysis_usage WHERE user_id = ? AND status = 'pending'",
            (user_id,),
        ).fetchone()["total"]
        if int(pending or 0) > 0:
            conn.rollback()
            return None, "An analysis is already processing for this account."

        used = conn.execute(
            """
            SELECT COUNT(*) AS total FROM portfolio_analysis_usage
            WHERE user_id = ? AND status IN ('pending', 'completed')
              AND created_at >= ? AND created_at < ?
            """,
            (user_id, start_utc, end_utc),
        ).fetchone()["total"]
        limit = int(subscription["limit"])
        if subscription["plan"] != "admin" and int(used or 0) >= limit:
            conn.rollback()
            return None, (
                "You have used all {} Portfolio Analyses available this month. "
                "Your allowance resets at the start of next month."
            ).format(limit)

        conn.execute(
            """
            INSERT INTO portfolio_analysis_usage
                (user_id, snapshot_id, report_type, status, reservation_token)
            VALUES (?, NULL, ?, 'pending', ?)
            """,
            (user_id, report_type, token),
        )
        conn.commit()
        return token, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_portfolio_analysis(reservation_token, snapshot_id):
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE portfolio_analysis_usage
            SET snapshot_id = ?, status = 'completed', error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE reservation_token = ? AND status = 'pending'
            """,
            (snapshot_id, reservation_token),
        )
        conn.commit()
        if cursor.rowcount != 1:
            raise RuntimeError("Analysis reservation could not be completed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fail_portfolio_analysis(reservation_token, error_message="Analysis failed"):
    if not reservation_token:
        return
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE portfolio_analysis_usage
            SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE reservation_token = ? AND status = 'pending'
            """,
            (str(error_message)[:500], reservation_token),
        )
        conn.commit()
    finally:
        conn.close()


def record_portfolio_analysis(user_id, snapshot_id, report_type):
    """Backward-compatible direct completed usage record."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO portfolio_analysis_usage
                (user_id, snapshot_id, report_type, status)
            VALUES (?, ?, ?, 'completed')
            """,
            (user_id, snapshot_id, report_type),
        )
        conn.commit()
    finally:
        conn.close()


def cleanup_failed_analysis(user_id, previous_snapshot_id=None):
    """Remove snapshots and report rows created after a failed single-user analysis job."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if previous_snapshot_id is None:
            rows = conn.execute(
                "SELECT id FROM portfolio_snapshots WHERE user_id = ?", (user_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id FROM portfolio_snapshots WHERE user_id = ? AND id > ?",
                (user_id, previous_snapshot_id),
            ).fetchall()
        snapshot_ids = [int(row["id"]) for row in rows]
        report_paths = []
        if snapshot_ids:
            placeholders = ",".join("?" for _ in snapshot_ids)
            params = [user_id] + snapshot_ids
            report_rows = conn.execute(
                "SELECT report_path FROM report_runs WHERE user_id = ? AND snapshot_id IN ({})".format(placeholders),
                params,
            ).fetchall()
            report_paths = [row["report_path"] for row in report_rows]
            conn.execute(
                "DELETE FROM report_runs WHERE user_id = ? AND snapshot_id IN ({})".format(placeholders),
                params,
            )
            conn.execute(
                "DELETE FROM recommendations WHERE user_id = ? AND snapshot_id IN ({})".format(placeholders),
                params,
            )
            conn.execute(
                "DELETE FROM portfolio_snapshots WHERE user_id = ? AND id IN ({})".format(placeholders),
                params,
            )
        conn.commit()
        return {"snapshot_ids": snapshot_ids, "report_paths": report_paths}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def login_attempt_is_limited(attempt_key, window_seconds=900, max_attempts=5):
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn = get_connection()
    try:
        conn.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (cutoff,))
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM login_attempts WHERE attempt_key = ?",
            (attempt_key,),
        ).fetchone()
        conn.commit()
        return int(row["total"] or 0) >= int(max_attempts)
    finally:
        conn.close()


def record_login_failure(attempt_key):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO login_attempts (attempt_key) VALUES (?)", (attempt_key,)
        )
        conn.commit()
    finally:
        conn.close()


def clear_login_failures(attempt_key):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (attempt_key,))
        conn.commit()
    finally:
        conn.close()


def update_last_login(user_id):
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_setting(key, default=None, user_id=None):
    conn = get_connection()
    try:
        if user_id is not None:
            row = conn.execute(
                "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
                (user_id, key),
            ).fetchone()
            if row:
                return row["value"]
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key, value, user_id=None):
    conn = get_connection()
    try:
        if user_id is None:
            conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
        else:
            conn.execute(
                "INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?, ?, ?)",
                (user_id, key, value),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_report_run(report_path, snapshot_id=None, status="success", message="Report generated", user_id=None):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO report_runs (user_id, snapshot_id, report_path, status, message) VALUES (?, ?, ?, ?, ?)",
            (user_id, snapshot_id, str(report_path), status, message),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_user_reports(user_id, limit=20):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, user_id, snapshot_id, report_path, status, message, created_at
            FROM report_runs
            WHERE user_id = ? AND status = 'success'
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, int(limit)),
        ).fetchall()
    finally:
        conn.close()


def get_user_report(report_id, user_id):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, user_id, snapshot_id, report_path, status, message, created_at
            FROM report_runs
            WHERE id = ? AND user_id = ? AND status = 'success'
            """,
            (report_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def update_user_billing(
    user_id,
    plan=None,
    stripe_customer_id=None,
    stripe_subscription_id=None,
    subscription_status=None,
):
    conn = get_connection()
    try:
        current = conn.execute(
            """
            SELECT plan, stripe_customer_id, stripe_subscription_id, subscription_status
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if not current:
            return
        resolved_plan = normalize_plan(plan if plan is not None else current["plan"])
        limit = monthly_analysis_limit(resolved_plan)
        stored_limit = int(limit if limit is not None else 999999)
        conn.execute(
            """
            UPDATE users
            SET plan = ?, subscription_plan = ?, monthly_analysis_limit = ?,
                stripe_customer_id = ?, stripe_subscription_id = ?,
                subscription_status = ?
            WHERE id = ?
            """,
            (
                resolved_plan,
                resolved_plan,
                stored_limit,
                stripe_customer_id if stripe_customer_id is not None else current["stripe_customer_id"],
                stripe_subscription_id if stripe_subscription_id is not None else current["stripe_subscription_id"],
                subscription_status if subscription_status is not None else current["subscription_status"],
                user_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def claim_stripe_event(event_id, event_type):
    """Claim a new/failed/stale Stripe event. Completed events remain duplicates."""
    if not event_id:
        return False
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, updated_at FROM stripe_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO stripe_events
                    (event_id, event_type, status, attempt_count, processed_at)
                VALUES (?, ?, 'processing', 1, NULL)
                """,
                (event_id, event_type or "unknown"),
            )
            conn.commit()
            return True
        if row["status"] == "completed":
            conn.rollback()
            return False
        if row["status"] == "processing":
            stale = conn.execute(
                "SELECT CASE WHEN ? < datetime('now', '-10 minutes') THEN 1 ELSE 0 END AS stale",
                (row["updated_at"],),
            ).fetchone()["stale"]
            if not stale:
                conn.rollback()
                return False
        conn.execute(
            """
            UPDATE stripe_events
            SET event_type = ?, status = 'processing', attempt_count = attempt_count + 1,
                error_message = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE event_id = ?
            """,
            (event_type or "unknown", event_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_stripe_event(event_id):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE stripe_events
            SET status = 'completed', processed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP, error_message = NULL
            WHERE event_id = ?
            """,
            (event_id,),
        )
        conn.commit()
    finally:
        conn.close()


def fail_stripe_event(event_id, error_message):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE stripe_events
            SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE event_id = ?
            """,
            (str(error_message)[:1000], event_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_stripe_event(event_id, event_type):
    """Compatibility alias for older callers."""
    return claim_stripe_event(event_id, event_type)


def get_user_by_stripe_customer(customer_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
    finally:
        conn.close()


def list_users_with_stats():
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT
                u.id, u.name, u.email, u.created_at, u.last_login,
                u.is_admin, u.plan, u.subscription_status,
                COUNT(DISTINCT ps.id) AS portfolio_count,
                COUNT(DISTINCT rr.id) AS report_count,
                COUNT(DISTINCT w.id) AS watchlist_count
            FROM users u
            LEFT JOIN portfolio_snapshots ps ON ps.user_id = u.id
            LEFT JOIN report_runs rr ON rr.user_id = u.id
            LEFT JOIN watchlist w ON w.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()


def get_admin_stats():
    conn = get_connection()
    try:
        users = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        paid = conn.execute(
            """
            SELECT COUNT(*) AS count FROM users
            WHERE plan IN ('pro', 'premium')
              AND subscription_status IN ('active', 'trialing')
            """
        ).fetchone()["count"]
        reports = conn.execute("SELECT COUNT(*) AS count FROM report_runs").fetchone()["count"]
        snapshots = conn.execute("SELECT COUNT(*) AS count FROM portfolio_snapshots").fetchone()["count"]
        return {"users": users, "paid_users": paid, "reports": reports, "snapshots": snapshots}
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    print("Database ready at {}".format(DB_PATH))
