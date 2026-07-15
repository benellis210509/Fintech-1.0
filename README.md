# Fintech Website — Final Build

A FastAPI portfolio research and educational-analysis application with user accounts, CSV uploads, portfolio dashboards, PDF reports, watchlists, account settings, admin controls, subscription limits and optional Stripe/OpenAI integration.

## What is included

- Separate user accounts and user-owned portfolio data
- Password hashing, CSRF protection, secure production cookies and security headers
- Free, Pro, Premium and Admin plan entitlements from one central configuration
- Atomic monthly-analysis reservations so concurrent requests cannot bypass limits
- Failed analyses do not consume allowance and partial data is removed
- Unique upload filenames to prevent collisions
- Single-currency CSV enforcement
- Database-owned report downloads with user ownership checks
- Consistent dark-only interface
- Database-backed login throttling
- Retry-safe Stripe webhook processing
- Persistent Render storage configuration
- Automated tests

## 1. Local setup on macOS

Open Terminal in this folder and run:

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn web_app:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8001
```

The app creates a clean SQLite database automatically.

## 2. Environment variables

Edit `.env` before production use.

Required in production:

```text
SESSION_SECRET
ADMIN_EMAIL
SUPPORT_EMAIL
PRIVACY_EMAIL
LEGAL_ENTITY_NAME
```

Optional AI commentary:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

Stripe test mode:

```text
PAID_PLANS_ENABLED=false
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
STRIPE_PRO_PRICE_ID
STRIPE_PREMIUM_PRICE_ID
```

Keep `PAID_PLANS_ENABLED=false` until checkout, portal, cancellation, failed-payment and webhook tests pass in Stripe test mode.

## 3. Admin access

Set this in `.env` or Render:

```text
ADMIN_EMAIL=your-email@example.com
```

An account created with that exact email is made an admin immediately. An existing account is promoted the next time it logs in.

You can also run:

```bash
python3 manage_admin.py
```

## 4. CSV format

A CSV must contain a ticker/symbol column and either:

- a market-value column, or
- both shares and price columns.

Recommended columns:

```text
Ticker,Company,Shares,Price,Value,CostBasis,Currency,Account,Sector
```

All monetary values in one upload must use one currency. Mixed-currency uploads are rejected because adding unconverted currencies would produce incorrect totals.

## 5. Tests

Install development dependencies and run:

```bash
pip install -r requirements-dev.txt
pytest -q
```

The included suite checks:

- plan limits
- Premium entitlements
- analysis reservation/refund behaviour
- Stripe event retries
- settings persistence
- monthly upload limits
- cross-user report protection

## 6. Render deployment

`render.yaml` is configured for:

- Python 3.11.9
- one Starter web service
- a 1 GB persistent disk at `/var/data`
- SQLite, uploads, charts and reports under `/var/data`
- a generated session secret
- secret prompts for admin, contact, OpenAI and Stripe values

Deploy through a Render Blueprint or create the service manually with the same settings.

The persistent disk is important. Do not change `STORAGE_DIR` or `DATABASE_PATH` back to the source-code folder on Render.

## 7. Before enabling public payments

Complete these checks in Stripe test mode:

1. Successful Pro checkout changes the account to Pro.
2. Successful Premium checkout changes the account to Premium.
3. Duplicate webhooks do not duplicate changes.
4. A temporarily failed webhook retries successfully.
5. Cancellation returns the account to Free at the appropriate time.
6. Failed or uncollectible payment removes paid access.
7. The billing portal opens for the correct customer.

## 8. Backups and privacy

Never share these files:

```text
.env
portfolio.db
portfolio.db-wal
portfolio.db-shm
reports/*.pdf
charts/*.png
data/*.csv
logs/*
```

The provided final ZIP contains none of the original user database, generated reports, generated charts, virtual environment or Git history.

## Important limitation

Fintech provides portfolio research and educational information. Snapshot value changes are not cash-flow-adjusted investment returns, and the application does not provide personalised financial advice or trading instructions.
