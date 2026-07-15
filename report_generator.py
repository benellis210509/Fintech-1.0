import os

from config import REPORTS_DIR, REPORT_NAME_PREFIX
from database import get_setting, get_user_subscription, insert_report_run
from plan_config import has_advanced_reports
from utils import timestamp_for_file

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer
except Exception:
    colors = None

from report_components import p
from report_sections import (
    allocation_section,
    cover_page,
    disclaimer,
    executive_dashboard,
    glossary,
    health_score_section,
    holding_detail,
    holdings_table,
    market_context,
    methodology,
    plain_language_summary,
    research_indicators,
    risk_review,
    structural_flags,
)
from report_styles import BORDER, GREEN, INK, MUTED, PAGE_MARGIN, make_styles


class BrandedCanvas(canvas.Canvas if colors else object):
    def __init__(self, *args, **kwargs):
        super(BrandedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_branding(page_count)
            super(BrandedCanvas, self).showPage()
        super(BrandedCanvas, self).save()

    def _draw_branding(self, page_count):
        self.saveState()
        width, height = letter

        self.setFillColor(colors.white)
        self.rect(0, height - 30, width, 30, stroke=0, fill=1)
        self.setFillColor(colors.HexColor(INK))
        self.setFont("Helvetica-Bold", 8)
        self.drawString(PAGE_MARGIN, height - 18, "FINTECH")
        self.setFillColor(colors.HexColor(MUTED))
        self.setFont("Helvetica", 7)
        self.drawRightString(width - PAGE_MARGIN, height - 18, "PORTFOLIO RESEARCH")
        self.setFillColor(colors.HexColor(GREEN))
        self.rect(0, height - 31, width, 1.5, stroke=0, fill=1)

        self.setStrokeColor(colors.HexColor(BORDER))
        self.line(PAGE_MARGIN, 45, width - PAGE_MARGIN, 45)
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor(MUTED))
        self.drawString(PAGE_MARGIN, 32, "General research and educational information")
        self.drawRightString(width - PAGE_MARGIN, 32, "Page {} of {}".format(self._pageNumber, page_count))
        self.restoreState()


def generate_report(summary, recommendations, chart_paths=None, output_filename=None, user_id=None):
    if colors is None:
        raise ImportError("reportlab is required. Run: pip install reportlab")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    subscription = get_user_subscription(user_id) if user_id else {"plan": "free", "limit": 1}
    plan = str(subscription.get("plan") or "free").strip().lower()
    pro_access = has_advanced_reports(plan)

    report_type = get_setting("report_type", "Full Report", user_id=user_id)
    benchmark_setting = get_setting("benchmark", "S&P 500", user_id=user_id)
    risk_profile = get_setting("risk_profile", "Moderate", user_id=user_id)

    # Free users cannot generate Deep Analysis, even if they alter the form manually.
    if not pro_access and report_type == "Deep Analysis":
        report_type = "Full Report"

    # Charts and recommendation content are Pro-only.
    chart_paths = (chart_paths or {}) if pro_access else {}
    report_recommendations = recommendations if pro_access else []

    if output_filename is None:
        output_filename = "user_{}_{}_{}.pdf".format(
            user_id or 0,
            REPORT_NAME_PREFIX,
            timestamp_for_file(),
        )

    target_path = REPORTS_DIR / os.path.basename(output_filename)
    styles = make_styles()

    doc = SimpleDocTemplate(
        str(target_path),
        pagesize=letter,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=53,
        bottomMargin=60,
        title="Fintech Portfolio Report",
        author="Fintech",
    )

    story = []

    cover_page(story, summary, report_type, styles)
    disclaimer(story, styles)
    story.append(Spacer(1, 18))

    # Core sections available to both Free and Pro.
    plain_language_summary(story, summary, styles, 1)
    executive_dashboard(story, summary, styles, 2)

    if not pro_access:
        # FREE REPORT
        # Excludes health score, risk warnings, recommendations, benchmark
        # comparison, PDF charts and all Deep Analysis sections.
        if report_type == "Quick Summary":
            allocation_section(
                story,
                summary,
                {},
                styles,
                include_gain_loss=False,
                number=3,
            )
            glossary(story, styles, 4)
        else:
            story.append(PageBreak())
            allocation_section(
                story,
                summary,
                {},
                styles,
                include_gain_loss=True,
                number=3,
            )
            holdings_table(story, summary, styles, 4)
            glossary(story, styles, 5)

    elif report_type == "Quick Summary":
        health_score_section(story, summary, chart_paths, styles, 3)
        structural_flags(story, summary, styles, 4)
        research_indicators(story, report_recommendations, styles, detailed=False, number=5)
        allocation_section(
            story,
            summary,
            chart_paths,
            styles,
            include_gain_loss=False,
            number=6,
        )
        glossary(story, styles, 7)

    elif report_type == "Full Report":
        story.append(PageBreak())
        health_score_section(story, summary, chart_paths, styles, 3)
        structural_flags(story, summary, styles, 4)
        allocation_section(
            story,
            summary,
            chart_paths,
            styles,
            include_gain_loss=True,
            number=5,
        )
        holdings_table(story, summary, styles, 6)

        story.append(PageBreak())
        risk_review(story, summary, risk_profile, styles, 7)
        research_indicators(story, report_recommendations, styles, detailed=True, number=8)
        market_context(story, summary, benchmark_setting, styles, 9)
        glossary(story, styles, 10)

    else:
        story.append(PageBreak())
        health_score_section(story, summary, chart_paths, styles, 3)
        structural_flags(story, summary, styles, 4)

        story.append(PageBreak())
        allocation_section(
            story,
            summary,
            chart_paths,
            styles,
            include_gain_loss=True,
            number=5,
        )
        holdings_table(story, summary, styles, 6)

        story.append(PageBreak())
        risk_review(story, summary, risk_profile, styles, 7)
        research_indicators(story, report_recommendations, styles, detailed=True, number=8)
        market_context(story, summary, benchmark_setting, styles, 9)
        holding_detail(story, report_recommendations, styles, 10)
        methodology(story, summary, styles, 11)
        glossary(story, styles, 12)

    story.append(Spacer(1, 14))
    plan_label = plan.title() if pro_access else "Free"
    story.append(
        p(
            (
                "Report settings: {} report, {} analysis sensitivity, {} benchmark. "
                "Subscription access: {}. Data sources may be delayed or unavailable. "
                "Verify important information independently."
            ).format(report_type, risk_profile, benchmark_setting, plan_label),
            styles["small"],
        )
    )

    doc.build(story, canvasmaker=BrandedCanvas)
    insert_report_run(
        str(target_path),
        summary.get("snapshot_id"),
        "success",
        "Report generated",
        user_id=user_id,
    )
    return str(target_path)
