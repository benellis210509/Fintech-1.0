import sys
import warnings

from ai_engine import generate_ai_commentary
from analytics import run_portfolio_analytics
from benchmark import benchmark_snapshot
from chart_engine import generate_all_charts
from csv_importer import import_csv
from database import create_tables, get_setting
from macro_data import get_macro_snapshot
from recommendation_engine import generate_recommendations
from report_generator import generate_report
from risk_engine import calculate_risk
from utils import setup_logging

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")


def run_pipeline(user_id=None, csv_path=None):
    setup_logging()
    if csv_path is None:
        snapshot_id = import_csv(user_id=user_id)
    else:
        snapshot_id = import_csv(csv_path=csv_path, user_id=user_id)

    summary = run_portfolio_analytics(snapshot_id, user_id=user_id)
    if not summary:
        raise RuntimeError("Analytics failed. Snapshot was not found.")

    risk_profile = get_setting("risk_profile", "Moderate", user_id=user_id)
    risk = calculate_risk(snapshot_id, summary, risk_profile)
    summary.update(risk)
    summary["benchmark"] = benchmark_snapshot(user_id=user_id)
    summary["macro"] = get_macro_snapshot()

    recommendations = generate_recommendations(snapshot_id, summary, user_id=user_id)
    summary["ai_commentary"] = generate_ai_commentary(summary, recommendations)
    chart_paths = generate_all_charts(snapshot_id, summary)
    return generate_report(
        summary,
        recommendations,
        chart_paths=chart_paths,
        user_id=user_id,
    )


if __name__ == "__main__":
    try:
        print(run_pipeline())
    except Exception as exc:
        import traceback
        print("ERROR:", exc)
        traceback.print_exc()
        sys.exit(1)
