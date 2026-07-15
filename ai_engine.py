import os

from dotenv import load_dotenv

load_dotenv()


def generate_ai_commentary(summary, indicators):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return fallback_commentary(summary, indicators)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        warnings = "\n".join(summary.get("warnings", [])) or "No major structural flags."
        indicator_text = "\n".join(
            "{}: {} ({}/100)".format(item["ticker"], item["action"], item["confidence"])
            for item in indicators
        ) or "No holding indicators were generated."

        prompt = """
Write a clear, neutral monthly portfolio research summary using only the data below.

Strict boundaries:
- Do not tell the user to buy, sell, hold, switch, rebalance, or invest in any product.
- Do not say a product is suitable for the user.
- Do not provide target prices, expected returns, forecasts, guarantees, or personalised financial advice.
- Describe concentrations, changes, missing data, and research questions in factual language.
- State that uploaded account-value changes are not investment performance because deposits,
  withdrawals, trades, fees, taxes, and foreign exchange movements are not adjusted for.
- State that market data can be delayed, incomplete, or inaccurate.
- Keep the output under 350 words.

Base currency: {currency}
Uploaded portfolio value: {value}
Structural risk score: {risk}
Risk band: {risk_level}
Structural flags:
{warnings}
Holding research indicators:
{indicators}
""".format(
            currency=summary.get("base_currency", "NZD"),
            value=summary.get("total_portfolio_value"),
            risk=summary.get("risk_score"),
            risk_level=summary.get("risk_level"),
            warnings=warnings,
            indicators=indicator_text,
        )

        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=550,
        )
        return response.choices[0].message.content
    except Exception:
        # Do not expose provider or internal exception details in user-facing reports.
        return fallback_commentary(summary, indicators)


def fallback_commentary(summary, indicators):
    currency = summary.get("base_currency", "NZD")
    value = float(summary.get("total_portfolio_value") or 0)
    risk = summary.get("risk_score", "N/A")
    level = summary.get("risk_level", "N/A")
    warnings = summary.get("warnings", [])
    warning_line = (
        " Structural flags include: " + "; ".join(warnings[:3])
        if warnings
        else " No major structural flags were triggered by the configured thresholds."
    )
    return (
        "The uploaded portfolio value is {} {:,.2f}. The structural risk score is {} / 100 "
        "({}).{} Changes between uploads are changes in reported account value, not calculated "
        "investment performance. Market and company data may be delayed, incomplete, or inaccurate."
    ).format(currency, value, risk, level, warning_line)
