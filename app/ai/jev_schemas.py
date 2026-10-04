"""Single-request Jev questions. Free text is produced by local policy only."""

from typing import Literal

from pydantic import BaseModel, Field

Comparison = Literal["below", "in_line", "above", "unknown"]


class FEDJudgments(BaseModel):
    is_fresh_release: bool = Field(
        description="Is this a newly announced FOMC rate decision, not a preview, minutes, speech or recap?"
    )
    actual_change_bp: Literal[-100, -75, -50, -25, 0, 25, 50, 75, 100] | None = Field(
        description="What signed rate change was actually announced in basis points? Hold is 0. Null if absent, ambiguous or outside these choices. Never infer the actual decision from expectations."
    )
    actual_narrative: Literal["hawkish", "dovish", "neutral", "mixed"] = Field(
        description="What is the monetary policy tone of the announcement?"
    )
    guidance_vs_baseline: Literal[
        "more_dovish", "in_line", "more_hawkish", "mixed", "unknown"
    ] = Field(
        description="Compare forward guidance with the expected narrative, excluding today's rate change. Mixed for conflicting guidance; unknown if insufficient."
    )


class CPIJudgments(BaseModel):
    is_fresh_release: bool = Field(
        description="Is this a newly published US BLS CPI release, not a preview, calendar, commentary or recap?"
    )
    headline_mom: Comparison = Field(
        description="Compare actual headline CPI month-on-month with expected_headline_cpi_mom. Below/above require at least 0.1 percentage point difference; otherwise in_line. Unknown if missing."
    )
    headline_yoy: Comparison = Field(
        description="Compare actual headline CPI year-on-year with expected_headline_cpi_yoy. Below/above require at least 0.1 percentage point difference; otherwise in_line. Unknown if missing."
    )
    core_mom: Comparison = Field(
        description="Compare actual core CPI month-on-month with expected_core_cpi_mom. Below/above require at least 0.1 percentage point difference; otherwise in_line. Unknown if missing."
    )
    core_yoy: Comparison = Field(
        description="Compare actual core CPI year-on-year with expected_core_cpi_yoy. Below/above require at least 0.1 percentage point difference; otherwise in_line. Unknown if missing."
    )


class NFPJudgments(BaseModel):
    is_fresh_release: bool = Field(
        description="Is this a newly published US BLS Employment Situation report, not a preview, calendar, commentary or recap?"
    )
    payrolls: Comparison = Field(
        description="Compare actual nonfarm payroll growth in thousands with expected_nonfarm_payrolls_k. Below/above require at least 30 thousand difference; otherwise in_line. Unknown if missing."
    )
    unemployment: Comparison = Field(
        description="Compare actual unemployment rate with expected_unemployment_rate. Below/above require at least 0.1 percentage point difference; otherwise in_line. Unknown if missing."
    )
    wages_mom: Comparison = Field(
        description="Compare actual average hourly earnings month-on-month with expected_average_hourly_earnings_mom. Below/above require at least 0.1 percentage point difference; otherwise in_line. Unknown if missing."
    )
    growth_scare: Literal["yes", "no", "unknown"] = Field(
        description="Does the report show a severe deterioration or recession shock likely to create risk-off pressure despite easing expectations? Unknown when unclear."
    )


class SocialJudgments(BaseModel):
    event_type: Literal[
        "tariff_escalation",
        "tariff_deescalation",
        "china_trade_conflict",
        "fed_pressure",
        "fiscal_policy",
        "crypto_policy_positive",
        "crypto_policy_negative",
        "geopolitical_risk",
        "company_specific",
        "non_tradeable",
    ] = Field(
        description="Classify the concrete catalyst in this Trump Truth Social post. Generic slogans, insults or political commentary are non_tradeable."
    )
    asset: Literal["btc", "broad_market", "usd", "none"] = Field(
        description="Which asset is directly affected? Use btc for crypto policy, broad_market for broad risk catalysts, none if no concrete financial effect."
    )
    concrete_new_action: bool = Field(
        description="Does this announce a concrete new action with a policy, number, target or timing, rather than a repeated position, boast, vague threat or already known plan? If novelty is not supported by the text, answer no."
    )
    transmission: Literal["risk_on", "risk_off", "mixed", "unknown"] = Field(
        description="Is the concrete catalyst likely to produce short-term Bitcoin risk_on or risk_off pressure? Tariff escalation and crypto restrictions are risk_off; tariff relief and concrete crypto adoption are risk_on. Mere Fed pressure is insufficient; conflicting channels are mixed."
    )
    time_sensitivity: Literal["immediate", "same_day", "slow", "none"] = Field(
        description="When can this new catalyst affect markets? Immediate for minutes, same_day for hours, slow for later, none if no actionable catalyst."
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="How high is the risk of reversal or conflicting interpretation?"
    )
