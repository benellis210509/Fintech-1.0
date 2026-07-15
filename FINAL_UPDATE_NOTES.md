# Final update notes

## Critical fixes completed

- Removed private database, reports, charts, virtual environment, `.git`, macOS metadata and caches from the distributable folder.
- Added persistent-storage support through `STORAGE_DIR` and `DATABASE_PATH`.
- Added a Render persistent disk configuration.
- Centralised Free, Pro, Premium and Admin entitlements in `plan_config.py`.
- Fixed Premium being treated as Free in parts of the application.
- Added atomic monthly-analysis reservations.
- Blocked concurrent analyses for the same user.
- Failed analyses now release allowance.
- Partial snapshots, recommendations, report rows, PDFs and charts are cleaned after failures.
- Unique filenames are used for every upload.
- Added user-friendly 400 and 413 upload responses.
- Fixed reversed watchlist edit/delete confirmation messages.
- Added ticker, company-name and notes length validation.
- Made the entire interface permanently dark-only.
- Added database-backed login throttling.
- Made Stripe webhook events retryable after processing failures.
- Synchronized legacy and current plan fields during billing updates.
- Changed report downloads to database-owned report IDs with strict user checks.
- Removed inline JavaScript and tightened the script Content Security Policy.
- Fixed immediate admin access for new accounts matching `ADMIN_EMAIL`.
- Added six passing automated tests.

## Test result

```text
6 passed
```
