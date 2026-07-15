from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", BASE_DIR)).expanduser().resolve()
DATA_DIR = STORAGE_DIR / "data"
REPORTS_DIR = STORAGE_DIR / "reports"
CHARTS_DIR = STORAGE_DIR / "charts"
LOGS_DIR = STORAGE_DIR / "logs"

DB_PATH = Path(
    os.environ.get("DATABASE_PATH", str(STORAGE_DIR / "portfolio.db"))
).expanduser().resolve()
CSV_PATH = DATA_DIR / "portfolio.csv"

REPORT_NAME_PREFIX = "portfolio_report"
BENCHMARK_TICKER = "^GSPC"
YAHOO_REFRESH_DAYS = 1

MAX_SINGLE_STOCK_WEIGHT = 0.30
MAX_SECTOR_WEIGHT = 0.45
MAX_TOP5_WEIGHT = 0.75
MAX_CASH_WEIGHT = 0.35
MIN_CASH_WEIGHT = 0.02

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "NZD").strip().upper() or "NZD"
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 5 * 1024 * 1024))
MAX_CSV_ROWS = int(os.environ.get("MAX_CSV_ROWS", 5000))
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Pacific/Auckland").strip() or "Pacific/Auckland"
TERMS_VERSION = os.environ.get("TERMS_VERSION", "2026-07-15")
APP_NAME = os.environ.get("APP_NAME", "Fintech")
LEGAL_ENTITY_NAME = os.environ.get("LEGAL_ENTITY_NAME", APP_NAME)
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "").strip()
PRIVACY_EMAIL = os.environ.get("PRIVACY_EMAIL", SUPPORT_EMAIL).strip()
PAID_PLANS_ENABLED = os.environ.get("PAID_PLANS_ENABLED", "false").lower() == "true"


def ensure_directories():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for path in (DATA_DIR, REPORTS_DIR, CHARTS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
