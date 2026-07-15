from reportlab.lib import colors
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from report_components import (
    add_chart, callout_box, insight_strip, metric_grid, notice_box, p,
    score_card, section_bar, table,
)
from report_styles import BORDER, BORDER_DARK, CONTENT_WIDTH, GREEN, GREEN_PALE, MUTED
from utils import format_currency, format_number


def pct_decimal(value):
    return "{:.1f}%".format(float(value or 0) * 100)


def signed_percent(value):
    return "{:+.2f}%".format(float(value or 0))


def available_percent(value):
    return "Unavailable" if value is None else signed_percent(value)


def available_number(value, decimals=2):
    return "Unavailable" if value is None else format_number(value, decimals)


def sentence(text):
    text = str(text or "").replace(";", ".").strip()
    if not text:
        return "Data was unavailable."
    parts = [part.strip() for part in text.split(".") if part.strip()]
    return ". ".join(part[:1].upper() + part[1:] for part in parts) + "."


def infer_score(summary):
    score_data = summary.get("portfolio_score") or {}
    if score_data.get("score") is not None:
        return score_data
    holdings = summary.get("holdings", [])
    count = len(holdings)
    max_weight = max([float(h.get("weight") or 0) for h in holdings] or [0]) * 100
    cash_pct = float(summary.get("cash_weight") or 0) * 100
    top5 = sum(sorted([float(h.get("weight") or 0) * 100 for h in holdings], reverse=True)[:5])
    diversification = 30 if count >= 15 else 24 if count >= 10 else 18 if count >= 6 else 10 if count >= 3 else 4
    concentration = 25 if max_weight <= 15 else 20 if max_weight <= 25 else 13 if max_weight <= 35 else 6
    cash = 20 if 5 <= cash_pct <= 15 else 15 if 2 <= cash_pct <= 25 else 8
    spread = 25 if top5 <= 55 else 20 if top5 <= 70 else 12 if top5 <= 85 else 5
    score = max(0, min(100, diversification + concentration + cash + spread))
    grade = "A+" if score >= 95 else "A" if score >= 90 else "A-" if score >= 85 else "B+" if score >= 80 else "B" if score >= 75 else "B-" if score >= 70 else "C" if score >= 60 else "Needs Attention"
    label = "Excellent" if score >= 90 else "Very Good" if score >= 80 else "Good" if score >= 70 else "Fair" if score >= 60 else "Needs Attention"
    return {
        "score": score, "grade": grade, "label": label,
        "categories": [
            {"name": "Diversification", "score": diversification, "maximum": 30},
            {"name": "Concentration", "score": concentration, "maximum": 25},
            {"name": "Cash allocation", "score": cash, "maximum": 20},
            {"name": "Position spread", "score": spread, "maximum": 25},
        ],
    }


def cover_page(story, summary, report_type, styles):
    titles = {
        "Quick Summary": "Portfolio Research Brief",
        "Full Report": "Portfolio Research Report",
        "Deep Analysis": "Portfolio Deep Analysis",
    }
    subtitles = {
        "Quick Summary": "A clear, beginner-friendly overview of portfolio structure and key research indicators.",
        "Full Report": "A detailed review of portfolio structure, holdings, gains, income and market context.",
        "Deep Analysis": "An expanded review with holding-level research, methodology and advanced portfolio analysis.",
    }
    score = infer_score(summary)
    story.append(Paragraph("FINTECH  /  PORTFOLIO RESEARCH", styles["cover_kicker"]))
    story.append(Paragraph(titles.get(report_type, titles["Full Report"]), styles["cover_title"]))
    story.append(Paragraph(subtitles.get(report_type, subtitles["Full Report"]), styles["cover_subtitle"]))

    story.append(metric_grid([
        ("Report date", str(summary.get("snapshot_date") or "Unavailable"), "Date of uploaded snapshot"),
        ("Portfolio value", format_currency(summary.get("total_portfolio_value")), "Uploaded account total"),
        ("Holdings", str(summary.get("holdings_count", 0)), "Non-cash positions"),
        ("Report type", report_type, "Selected detail level"),
    ], styles))
    story.append(Spacer(1, 9))

    score_box = score_card(score.get("score", 0), score.get("grade", "N/A"), score.get("label", "N/A"), styles)
    highlights = insight_strip([
        ("Largest position", pct_decimal(summary.get("max_position_weight"))),
        ("Cash allocation", pct_decimal(summary.get("cash_weight"))),
        ("Structure risk score", "{} / 100".format(summary.get("risk_score", "N/A"))),
    ], styles)
    outer = Table([[score_box, highlights]], colWidths=[180, 348], hAlign="LEFT")
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(outer)
    story.append(Spacer(1, 14))


def disclaimer(story, styles):
    text = (
        "This report provides general research and educational information only. It does not consider complete financial circumstances, goals, tax position, time horizon, liquidity needs or product suitability. Research labels are mechanical indicators, not recommendations to buy, sell or hold. Market data may be delayed, incomplete or inaccurate."
    )
    story.append(notice_box(text, styles))


def plain_language_summary(story, summary, styles, number=1):
    story.append(section_bar("Plain-language summary", styles, number))
    story.append(Spacer(1, 13))
    largest = summary.get("holdings", [{}])[0] if summary.get("holdings") else {}
    largest_ticker = largest.get("ticker") or "The largest holding"
    text = (
        "The uploaded portfolio contains {} holdings with a total value of {}. {} represents {} of the portfolio. The five largest holdings represent {} and cash represents {}. These figures describe structure and concentration. They do not show whether the portfolio is suitable for any person."
    ).format(
        summary.get("holdings_count", 0), format_currency(summary.get("total_portfolio_value")),
        largest_ticker, pct_decimal(summary.get("max_position_weight")),
        pct_decimal(summary.get("top5_weight")), pct_decimal(summary.get("cash_weight")),
    )
    story.append(p(text, styles["body"]))


def executive_dashboard(story, summary, styles, number=2):
    story.append(section_bar("Executive overview", styles, number))
    story.append(Spacer(1, 13))
    story.append(metric_grid([
        ("Total portfolio", format_currency(summary.get("total_portfolio_value")), "Equity plus cash"),
        ("Equity value", format_currency(summary.get("equity_value")), "Invested holdings"),
        ("Cash", format_currency(summary.get("cash_balance")), pct_decimal(summary.get("cash_weight")) + " of portfolio"),
        ("Holdings", str(summary.get("holdings_count", 0)), "Individual positions"),
        ("Value change", "{} ({})".format(format_currency(summary.get("mom_change_usd")), signed_percent(summary.get("mom_change_pct") or 0)), "Between uploads"),
        ("Estimated dividends", format_currency(summary.get("dividend_income")), "Indicative annual amount"),
        ("Indicative yield", "{:.2f}%".format(summary.get("portfolio_yield") or 0), "Based on available data"),
        ("Structure risk", "{} / 100".format(summary.get("risk_score", "N/A")), "Higher means more flags"),
    ], styles))
    story.append(p("Value change compares uploaded account totals. It is not investment performance and does not adjust for deposits, withdrawals, trades, fees, tax or foreign exchange movements.", styles["small"]))


def health_score_section(story, summary, chart_paths, styles, number=3):
    score = infer_score(summary)
    story.append(section_bar("Portfolio health score", styles, number))
    story.append(Spacer(1, 13))
    meanings = {
        "Diversification": "Number of holdings and dependence on the largest position.",
        "Concentration": "How much value is held in the largest positions.",
        "Cash allocation": "How recorded cash compares with a broad analysis range.",
        "Position spread": "How evenly value is distributed across positions.",
    }
    rows = [[p("Category", styles["table_head"]), p("Score", styles["table_head"]), p("Plain-English meaning", styles["table_head"])]]
    for item in score.get("categories", []):
        rows.append([
            p(item.get("name", ""), styles["table_cell_bold"]),
            p("{} / {}".format(item.get("score", 0), item.get("maximum", 0)), styles["table_cell"]),
            p(meanings.get(item.get("name"), "A mechanical portfolio structure measure."), styles["table_cell"]),
        ])
    story.append(table(rows, widths=[145, 82, 301], compact=True))
    add_chart(story, chart_paths, "portfolio_score", "Portfolio health categories. A longer green bar indicates a stronger result under the stated mechanical method.", height=2.45)
    story.append(callout_box(
        "What this means",
        "The Portfolio Health Score is an educational measure of structure and concentration. It does not predict returns and does not assess personal suitability.",
        styles,
    ))


def structural_flags(story, summary, styles, number=4):
    warnings = summary.get("warnings") or []
    story.append(section_bar("Portfolio structure alerts", styles, number))
    story.append(Spacer(1, 13))
    if not warnings:
        story.append(callout_box("What this means", "No structure alerts were triggered using the selected analysis thresholds.", styles))
        return
    rows = [[p("Observation", styles["table_head"]), p("What this means", styles["table_head"])]]
    for warning in warnings:
        rows.append([
            p(sentence(warning), styles["table_cell"]),
            p("This measure is above a selected analysis threshold, so changes in this area may have a larger effect on the portfolio.", styles["table_cell"]),
        ])
    story.append(table(rows, widths=[318, 210], compact=True))


def allocation_section(story, summary, chart_paths, styles, include_gain_loss=False, number=5):
    story.append(section_bar("Portfolio allocation", styles, number))
    story.append(Spacer(1, 13))
    if not add_chart(story, chart_paths, "allocation", "Largest holdings by uploaded market value. Percentages show each holding's share of the portfolio.", height=2.75):
        story.append(callout_box("Chart unavailable", "The allocation chart could not be generated.", styles, tone="neutral"))
    if include_gain_loss:
        add_chart(story, chart_paths, "gain_loss", "Reported unrealized gains and losses calculated from uploaded cost-basis data.", height=2.35)
    meaningful = [s for s in summary.get("sector_weights", []) if str(s.get("sector") or "").strip().lower() not in ("", "unknown", "unknown sector")]
    if meaningful:
        add_chart(story, chart_paths, "sector", "Sector exposure based on available third-party classification data.", height=2.35)
    else:
        story.append(callout_box("Sector data unavailable", "A sector chart was not shown because reliable sector classifications were unavailable for most holdings.", styles, tone="neutral"))


def holdings_table(story, summary, styles, number=6):
    story.append(section_bar("Detailed holdings", styles, number))
    story.append(Spacer(1, 13))
    rows = [[
        p("Ticker", styles["table_head"]), p("Company", styles["table_head"]),
        p("Shares", styles["table_head"]), p("Price", styles["table_head"]),
        p("Value", styles["table_head"]), p("Weight", styles["table_head"]),
        p("Reported gain/loss", styles["table_head"]),
    ]]
    for h in summary.get("holdings", []):
        rows.append([
            p(h.get("ticker", ""), styles["table_cell_bold"]),
            p(h.get("company_name", ""), styles["table_cell"]),
            p(format_number(h.get("shares"), 2), styles["table_cell"]),
            p(format_currency(h.get("price")), styles["table_cell"]),
            p(format_currency(h.get("market_value")), styles["table_cell_bold"]),
            p(pct_decimal(h.get("weight")), styles["table_cell"]),
            p("{} ({:+.1f}%)".format(format_currency(h.get("unrealized_gain_loss")), h.get("unrealized_gain_loss_pct") or 0), styles["table_cell"]),
        ])
    story.append(table(rows, widths=[42, 124, 46, 59, 66, 48, 143], compact=True))


def risk_review(story, summary, risk_profile, styles, number=7):
    story.append(section_bar("Portfolio structure review", styles, number))
    story.append(Spacer(1, 13))
    rows = [
        [p("Measure", styles["table_head"]), p("Result", styles["table_head"]), p("Simple meaning", styles["table_head"])],
        [p("Analysis sensitivity", styles["table_cell_bold"]), p(risk_profile, styles["table_cell"]), p("The selected warning threshold set. It is not personal risk tolerance.", styles["table_cell"])],
        [p("Structure risk score", styles["table_cell_bold"]), p("{} / 100".format(summary.get("risk_score", "N/A")), styles["table_cell"]), p("Higher values generally mean more concentration or more triggered thresholds.", styles["table_cell"])],
        [p("Concentration index", styles["table_cell_bold"]), p(str(summary.get("hhi", "N/A")), styles["table_cell"]), p("A technical measure of concentration. Higher values mean more concentration.", styles["table_cell"])],
        [p("Largest position", styles["table_cell_bold"]), p(pct_decimal(summary.get("max_position_weight")), styles["table_cell"]), p("The share of portfolio value in the largest holding.", styles["table_cell"])],
        [p("Top five holdings", styles["table_cell_bold"]), p(pct_decimal(summary.get("top5_weight")), styles["table_cell"]), p("The share of portfolio value in the five largest holdings.", styles["table_cell"])],
        [p("Cash allocation", styles["table_cell_bold"]), p(pct_decimal(summary.get("cash_weight")), styles["table_cell"]), p("The share of portfolio value recorded as cash.", styles["table_cell"])],
    ]
    story.append(table(rows, widths=[146, 92, 290], compact=True))


def research_indicators(story, recommendations, styles, detailed=True, number=8):
    story.append(section_bar("Holding research indicators", styles, number))
    story.append(Spacer(1, 13))
    story.append(p("These mechanical labels use available valuation, income, volatility and concentration data. They are not instructions, forecasts or personal recommendations.", styles["body"]))
    if detailed:
        rows = [[p("Ticker", styles["table_head"]), p("Research label", styles["table_head"]), p("Score", styles["table_head"]), p("Key observations", styles["table_head"])]]
        for item in recommendations:
            rows.append([
                p(item.get("ticker", ""), styles["table_cell_bold"]),
                p(item.get("classification") or item.get("action") or "Data unavailable", styles["table_cell"]),
                p("{:.0f}/100".format(item.get("score", item.get("confidence")) or 0), styles["table_cell"]),
                p(sentence(item.get("reasoning")), styles["table_cell"]),
            ])
        story.append(table(rows, widths=[48, 128, 58, 294], compact=True))
    else:
        rows = [[p("Ticker", styles["table_head"]), p("Research label", styles["table_head"]), p("Score", styles["table_head"])]]
        for item in recommendations:
            rows.append([
                p(item.get("ticker", ""), styles["table_cell_bold"]),
                p(item.get("classification") or item.get("action") or "Data unavailable", styles["table_cell"]),
                p("{:.0f}/100".format(item.get("score", item.get("confidence")) or 0), styles["table_cell"]),
            ])
        story.append(table(rows, widths=[85, 327, 116], compact=True))


def market_context(story, summary, benchmark_setting, styles, number=9):
    bench = summary.get("benchmark") or {}
    macro = summary.get("macro") or {}
    benchmark_available = any(bench.get(key) is not None for key in ("return_1m", "return_3m", "return_1y"))
    macro_available = any(macro.get(key) is not None for key in ("vix", "ten_year_yield", "sp500_1m"))
    story.append(section_bar("Benchmark and market context", styles, number))
    story.append(Spacer(1, 13))
    if benchmark_available:
        story.append(table([
            [p("Benchmark", styles["table_head"]), p("1 month", styles["table_head"]), p("3 months", styles["table_head"]), p("1 year", styles["table_head"])],
            [p("{} ({})".format(benchmark_setting, bench.get("ticker", "")), styles["table_cell_bold"]), p(available_percent(bench.get("return_1m")), styles["table_cell"]), p(available_percent(bench.get("return_3m")), styles["table_cell"]), p(available_percent(bench.get("return_1y")), styles["table_cell"])],
        ], widths=[216, 104, 104, 104], compact=True))
    else:
        story.append(callout_box("Benchmark data unavailable", "Benchmark returns were not available when this report was generated. The section is shortened instead of showing repeated unavailable values.", styles, tone="neutral"))
    if macro_available:
        story.append(Spacer(1, 12))
        story.append(table([
            [p("Market setting", styles["table_head"]), p("VIX", styles["table_head"]), p("10-year yield", styles["table_head"]), p("S&P 500 1 month", styles["table_head"])],
            [p(macro.get("regime") or "Not assessed", styles["table_cell"]), p(available_number(macro.get("vix")), styles["table_cell"]), p(available_number(macro.get("ten_year_yield")), styles["table_cell"]), p(available_percent(macro.get("sp500_1m")), styles["table_cell"])],
        ], widths=[216, 104, 104, 104], compact=True))
    if macro.get("note"):
        story.append(Spacer(1, 9))
        story.append(p(macro.get("note"), styles["small"]))


def holding_detail(story, recommendations, styles, number=10):
    story.append(section_bar("Holding-level research detail", styles, number))
    story.append(Spacer(1, 13))
    for item in recommendations:
        title = "{}  |  {}".format(item.get("ticker", ""), item.get("classification") or item.get("action") or "Data unavailable")
        card = Table([
            [p(title, styles["holding_title"])],
            [table([
                [p("Research score", styles["table_head"]), p("Key observations", styles["table_head"])],
                [p("{:.0f}/100".format(item.get("score", item.get("confidence")) or 0), styles["table_cell_bold"]), p(sentence(item.get("reasoning")), styles["table_cell"])],
            ], widths=[112, 392], compact=True)],
        ], colWidths=[CONTENT_WIDTH])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F7F7F7")),
            ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(GREEN)),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ]))
        story.append(KeepTogether([card, Spacer(1, 9)]))


def methodology(story, summary, styles, number=11):
    story.append(section_bar("Methodology and selected limits", styles, number))
    story.append(Spacer(1, 13))
    limits = summary.get("risk_limits") or {}
    if limits:
        labels = {
            "max_single_stock": "Maximum single holding",
            "max_sector": "Maximum sector exposure",
            "max_top5": "Maximum top five exposure",
            "max_cash": "Maximum cash allocation",
            "min_cash": "Minimum cash allocation",
        }
        rows = [[p("Threshold", styles["table_head"]), p("Configured value", styles["table_head"])]]
        for key, value in limits.items():
            rows.append([p(labels.get(key, str(key).replace("_", " ").title()), styles["table_cell_bold"]), p(pct_decimal(value), styles["table_cell"])])
        story.append(table(rows, widths=[330, 198], compact=True))
    story.append(Spacer(1, 12))
    story.append(callout_box("How to read this section", "These thresholds are user-selected analysis settings. They are not personal investment limits, predictions or instructions.", styles))


def glossary(story, styles, number=12):
    story.append(section_bar("Glossary and limitations", styles, number))
    story.append(Spacer(1, 13))
    rows = [
        [p("Term", styles["table_head"]), p("Simple meaning", styles["table_head"])],
        [p("Value change", styles["table_cell_bold"]), p("The difference between uploaded account totals. It is not investment performance.", styles["table_cell"])],
        [p("Portfolio weight", styles["table_cell_bold"]), p("The percentage of uploaded portfolio value in a holding, sector or cash.", styles["table_cell"])],
        [p("Structure risk score", styles["table_cell_bold"]), p("A mechanical concentration and threshold score. It is not personal risk profiling.", styles["table_cell"])],
        [p("Research label", styles["table_cell_bold"]), p("A limited mechanical data label. It is not an instruction, forecast or suitability assessment.", styles["table_cell"])],
        [p("Benchmark", styles["table_cell_bold"]), p("A reference index. The comparison does not adjust for cash flows, currency, fees or tax.", styles["table_cell"])],
    ]
    story.append(table(rows, widths=[155, 373], compact=True))
