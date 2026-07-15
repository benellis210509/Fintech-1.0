# chart_engine.py

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from config import CHARTS_DIR


# =========================================================
# COLOUR SYSTEM
# =========================================================

DARK_GREEN = "#166534"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"
TRACK = "#ECEFED"
WHITE = "#FFFFFF"


# =========================================================
# FORMATTERS
# =========================================================

def _money_axis(value, _position):
    if abs(value) >= 1_000_000:
        return "${:.1f}m".format(value / 1_000_000)

    if abs(value) >= 1_000:
        return "${:.1f}k".format(value / 1_000)

    return "${:,.0f}".format(value)


def _percent_axis(value, _position):
    return "{:.0f}%".format(value)


# =========================================================
# SHARED CHART STYLING
# =========================================================

def _style_chart(ax, title, show_grid=True):
    ax.set_title(
        title,
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=TEXT,
        pad=18,
    )

    ax.set_axisbelow(True)

    if show_grid:
        ax.grid(
            axis="x",
            color=GRID,
            linewidth=0.8,
        )
    else:
        ax.grid(False)

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)

    ax.spines["bottom"].set_color(GRID)
    ax.spines["bottom"].set_linewidth(0.8)

    ax.tick_params(
        axis="y",
        length=0,
        labelsize=9,
        colors=TEXT,
        pad=8,
    )

    ax.tick_params(
        axis="x",
        labelsize=8,
        colors=MUTED,
    )

    ax.set_facecolor(WHITE)


def _finish(fig, path):
    fig.patch.set_facecolor(WHITE)

    fig.tight_layout(
        pad=1.6,
    )

    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
        facecolor=WHITE,
        edgecolor="none",
    )

    plt.close(fig)

    return str(path)


def _add_bar_labels(
    ax,
    bars,
    labels,
    text_colour=TEXT,
):
    maximum = max(
        [abs(bar.get_width()) for bar in bars],
        default=0,
    )

    spacing = maximum * 0.025 if maximum else 1

    for bar, label in zip(bars, labels):
        width = bar.get_width()

        if width >= 0:
            x_position = width + spacing
            alignment = "left"
        else:
            x_position = width - spacing
            alignment = "right"

        ax.text(
            x_position,
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            ha=alignment,
            fontsize=8.5,
            fontweight="bold",
            color=text_colour,
        )


# =========================================================
# CHART GENERATION
# =========================================================

def generate_all_charts(snapshot_id, summary):
    CHARTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = {}

    holdings = summary.get("holdings", [])

    # -----------------------------------------------------
    # LARGEST HOLDINGS
    # -----------------------------------------------------

    if holdings:
        top_holdings = sorted(
            holdings,
            key=lambda holding: float(
                holding.get("market_value") or 0
            ),
            reverse=True,
        )[:10]

        top_holdings = list(
            reversed(top_holdings)
        )

        labels = [
            holding.get("ticker", "")
            for holding in top_holdings
        ]

        values = [
            float(
                holding.get("market_value") or 0
            )
            for holding in top_holdings
        ]

        weights = [
            float(
                holding.get("weight") or 0
            ) * 100
            for holding in top_holdings
        ]

        fig_height = max(
            3.4,
            len(labels) * 0.48 + 1.5,
        )

        fig, ax = plt.subplots(
            figsize=(8.4, fig_height)
        )

        bars = ax.barh(
            labels,
            values,
            color=DARK_GREEN,
            height=0.56,
        )

        _style_chart(
            ax,
            "Largest holdings by market value",
        )

        ax.xaxis.set_major_formatter(
            FuncFormatter(_money_axis)
        )

        value_labels = [
            "{}  |  {:.1f}%".format(
                _money_axis(value, None),
                weight,
            )
            for value, weight in zip(
                values,
                weights,
            )
        ]

        _add_bar_labels(
            ax,
            bars,
            value_labels,
        )

        maximum = max(values, default=0)

        if maximum:
            ax.set_xlim(
                0,
                maximum * 1.25,
            )

        path = (
            CHARTS_DIR
            / "allocation_{}.png".format(
                snapshot_id
            )
        )

        paths["allocation"] = _finish(
            fig,
            path,
        )

        # -------------------------------------------------
        # REPORTED UNREALIZED GAIN AND LOSS
        # -------------------------------------------------

        gain_rows = [
            holding
            for holding in top_holdings
            if holding.get(
                "unrealized_gain_loss"
            ) is not None
        ]

        if gain_rows:
            gain_rows = sorted(
                gain_rows,
                key=lambda holding: float(
                    holding.get(
                        "unrealized_gain_loss"
                    )
                    or 0
                ),
            )

            gain_labels = [
                holding.get("ticker", "")
                for holding in gain_rows
            ]

            gain_values = [
                float(
                    holding.get(
                        "unrealized_gain_loss"
                    )
                    or 0
                )
                for holding in gain_rows
            ]

            fig_height = max(
                3.2,
                len(gain_labels) * 0.48 + 1.5,
            )

            fig, ax = plt.subplots(
                figsize=(8.4, fig_height)
            )

            bars = ax.barh(
                gain_labels,
                gain_values,
                color=DARK_GREEN,
                height=0.56,
            )

            ax.axvline(
                0,
                color=MUTED,
                linewidth=0.8,
            )

            _style_chart(
                ax,
                "Reported unrealized gain and loss",
            )

            ax.xaxis.set_major_formatter(
                FuncFormatter(_money_axis)
            )

            gain_text = [
                _money_axis(value, None)
                for value in gain_values
            ]

            _add_bar_labels(
                ax,
                bars,
                gain_text,
            )

            largest_absolute = max(
                [
                    abs(value)
                    for value in gain_values
                ],
                default=0,
            )

            if largest_absolute:
                minimum_value = min(
                    gain_values
                )
                maximum_value = max(
                    gain_values
                )

                padding = (
                    largest_absolute * 0.2
                )

                ax.set_xlim(
                    min(0, minimum_value)
                    - padding,
                    max(0, maximum_value)
                    + padding,
                )

            path = (
                CHARTS_DIR
                / "gain_loss_{}.png".format(
                    snapshot_id
                )
            )

            paths["gain_loss"] = _finish(
                fig,
                path,
            )

    # -----------------------------------------------------
    # SECTOR EXPOSURE
    # -----------------------------------------------------

    sectors = summary.get(
        "sector_weights",
        [],
    )

    meaningful_sectors = [
        sector
        for sector in sectors
        if str(
            sector.get("sector") or ""
        ).strip().lower()
        not in (
            "",
            "unknown",
            "unknown sector",
        )
    ]

    if meaningful_sectors:
        meaningful_sectors = sorted(
            meaningful_sectors,
            key=lambda sector: float(
                sector.get("market_value") or 0
            ),
            reverse=True,
        )[:10]

        meaningful_sectors = list(
            reversed(meaningful_sectors)
        )

        sector_labels = [
            sector.get("sector", "")
            for sector in meaningful_sectors
        ]

        sector_values = [
            float(
                sector.get("weight") or 0
            ) * 100
            for sector in meaningful_sectors
        ]

        fig_height = max(
            3.2,
            len(sector_labels) * 0.48 + 1.5,
        )

        fig, ax = plt.subplots(
            figsize=(8.4, fig_height)
        )

        bars = ax.barh(
            sector_labels,
            sector_values,
            color=DARK_GREEN,
            height=0.56,
        )

        _style_chart(
            ax,
            "Sector exposure",
        )

        ax.xaxis.set_major_formatter(
            FuncFormatter(_percent_axis)
        )

        sector_text = [
            "{:.1f}%".format(value)
            for value in sector_values
        ]

        _add_bar_labels(
            ax,
            bars,
            sector_text,
        )

        maximum = max(
            sector_values,
            default=0,
        )

        ax.set_xlim(
            0,
            max(
                100,
                maximum * 1.15,
            ),
        )

        path = (
            CHARTS_DIR
            / "sector_{}.png".format(
                snapshot_id
            )
        )

        paths["sector"] = _finish(
            fig,
            path,
        )

    # -----------------------------------------------------
    # PORTFOLIO HEALTH SCORE
    # -----------------------------------------------------

    score_data = (
        summary.get("portfolio_score")
        or {}
    )

    categories = (
        score_data.get("categories")
        or []
    )

    if categories:
        categories = list(
            reversed(categories)
        )

        score_labels = [
            category.get("name", "")
            for category in categories
        ]

        score_percentages = [
            100
            * float(
                category.get("score") or 0
            )
            / max(
                float(
                    category.get(
                        "maximum"
                    )
                    or 1
                ),
                1,
            )
            for category in categories
        ]

        fig_height = max(
            3.2,
            len(score_labels) * 0.5 + 1.5,
        )

        fig, ax = plt.subplots(
            figsize=(8.4, fig_height)
        )

        ax.barh(
            score_labels,
            [100] * len(score_labels),
            color=TRACK,
            height=0.52,
        )

        bars = ax.barh(
            score_labels,
            score_percentages,
            color=DARK_GREEN,
            height=0.52,
        )

        _style_chart(
            ax,
            "Portfolio Health Score",
            show_grid=False,
        )

        ax.set_xlim(
            0,
            100,
        )

        ax.xaxis.set_major_formatter(
            FuncFormatter(_percent_axis)
        )

        score_text = [
            "{:.0f}%".format(value)
            for value in score_percentages
        ]

        for bar, label in zip(
            bars,
            score_text,
        ):
            width = bar.get_width()

            if width >= 18:
                x_position = width - 2
                alignment = "right"
                text_colour = WHITE
            else:
                x_position = width + 2
                alignment = "left"
                text_colour = TEXT

            ax.text(
                x_position,
                bar.get_y()
                + bar.get_height() / 2,
                label,
                va="center",
                ha=alignment,
                fontsize=8.5,
                fontweight="bold",
                color=text_colour,
            )

        for side in (
            "top",
            "right",
            "left",
            "bottom",
        ):
            ax.spines[side].set_visible(
                False
            )

        path = (
            CHARTS_DIR
            / "portfolio_score_{}.png".format(
                snapshot_id
            )
        )

        paths["portfolio_score"] = _finish(
            fig,
            path,
        )

    return paths