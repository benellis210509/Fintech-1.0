from yahoo_data import get_price_history_return


def get_macro_snapshot():
    """Return only data the app actually retrieves; never use fake zero placeholders."""
    return {
        "regime": "not assessed",
        "vix": None,
        "ten_year_yield": None,
        "sp500_1m": get_price_history_return("^GSPC", "1mo"),
        "note": (
            "The current version does not retrieve a complete macroeconomic dataset. "
            "Any available market return is third-party data and may be delayed or incomplete."
        ),
    }
