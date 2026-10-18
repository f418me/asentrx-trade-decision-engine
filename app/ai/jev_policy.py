"""Deterministic signal policy; Jev confidence measures answers, not returns."""

import math
import re

from app.models import (
    AnalysisAbstention,
    FEDDecisionImpact,
    CPIReportImpact,
    NFPReportImpact,
    SocialMediaMarketSignal,
)


class Abstain(ValueError):
    pass


def field_confidence(details, fields, threshold):
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("JEV_CONFIDENCE_THRESHOLD must be finite and between 0 and 1")
    confidence = details.get("confidence") if isinstance(details, dict) else None
    if not isinstance(confidence, dict):
        raise Abstain("Missing provider confidence.")
    values = [confidence.get(name) for name in fields]
    if any(
        type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
        for v in values
    ):
        raise Abstain("Missing or invalid confidence for a required answer.")
    minimum = min(values)
    if minimum < threshold:
        raise Abstain("A required answer is below the Jev confidence threshold.")
    return minimum


def baseline_change(expectations):
    amount = expectations.expected_interest_rate_change_amount or ""
    if not re.fullmatch(r"[+-]?\d+bp", amount):
        raise ValueError("FED baseline needs a signed basis-point amount, e.g. +25bp")
    change = int(amount[:-2])
    direction = "increase" if change > 0 else "decrease" if change < 0 else "hold"
    if direction != expectations.expected_interest_rate_change_type:
        raise ValueError("FED baseline direction and amount disagree")
    return change


def decide(source, answers, baseline, details, threshold):
    try:
        return _decide(source, answers, baseline, details, threshold)
    except Abstain as exc:
        return AnalysisAbstention(source=source, reason=str(exc))


def _decide(source, answers, baseline, details, threshold):
    if source == "social":
        return _social(answers, details, threshold)

    field_confidence(details, ["is_fresh_release"], threshold)
    if not answers.is_fresh_release:
        raise Abstain("Not a fresh official release.")
    required = ["is_fresh_release"]
    if source == "fed":
        if answers.actual_change_bp is None:
            raise Abstain("Announced rate change is unknown or unsupported.")
        surprise = answers.actual_change_bp - baseline_change(baseline)
        required.append("actual_change_bp")
        if surprise == 0:
            required.append("guidance_vs_baseline")
        confidence = field_confidence(details, required, threshold)
        if surprise:
            impact = "positive" if surprise < 0 else "negative"
            reason = f"Rate surprise: {surprise:+d}bp; takes priority over guidance."
        else:
            if answers.guidance_vs_baseline == "unknown":
                raise Abstain("Rate matches baseline but guidance is unknown.")
            impact = {
                "more_dovish": "positive",
                "more_hawkish": "negative",
                "in_line": "neutral",
                "mixed": "neutral",
            }[answers.guidance_vs_baseline]
            reason = f"Rate matches baseline; guidance: {answers.guidance_vs_baseline}."
        change = answers.actual_change_bp
        return FEDDecisionImpact(
            impact_on_bitcoin=impact,
            confidence=confidence,
            reasoning=reason,
            actual_fed_decision_summary=f"Announced rate change: {change:+d}bp; tone: {answers.actual_narrative}.",
            actual_interest_rate_change_type="increase"
            if change > 0
            else "decrease"
            if change < 0
            else "hold",
            actual_interest_rate_change_amount=f"{change:+d}bp" if change else "0bp",
            actual_narrative=answers.actual_narrative,
        )

    if source == "cpi":
        fields = ["headline_mom", "headline_yoy", "core_mom", "core_yoy"]
    else:
        fields = ["payrolls", "unemployment", "wages_mom", "growth_scare"]
    confidence = field_confidence(details, required + fields, threshold)
    comparisons = {name: getattr(answers, name) for name in fields}
    if "unknown" in comparisons.values():
        raise Abstain("A required release comparison is unknown.")
    reason = "; ".join(f"{name}={value}" for name, value in comparisons.items())
    impact = "neutral"
    if source == "cpi":
        values = set(comparisons.values())
        # A core surprise is required; conflicting headline/core measures veto direction.
        core = {answers.core_mom, answers.core_yoy}
        if "below" in core and "above" not in values:
            impact = "positive"
        elif "above" in core and "below" not in values:
            impact = "negative"
        cls = CPIReportImpact
    else:
        if answers.growth_scare == "no":
            if (
                answers.payrolls == answers.wages_mom == "below"
                and answers.unemployment in ("above", "in_line")
            ):
                impact = "positive"
            elif (
                answers.payrolls == answers.wages_mom == "above"
                and answers.unemployment in ("below", "in_line")
            ):
                impact = "negative"
        cls = NFPReportImpact
    # Numeric actual_* fields remain null: Jev compared values, it did not extract them.
    return cls(
        impact_on_bitcoin=impact,
        confidence=confidence,
        reasoning=reason,
        actual_report_summary=reason,
    )


def _social(answers, details, threshold):
    confidence = field_confidence(
        details,
        [
            "event_type",
            "asset",
            "concrete_new_action",
            "transmission",
            "time_sensitivity",
        ],
        threshold,
    )
    reason = f"{answers.event_type}; transmission={answers.transmission}; timing={answers.time_sensitivity}"
    veto = None
    if not answers.concrete_new_action:
        veto = "No supported concrete new action."
    elif answers.event_type in (
        "company_specific",
        "non_tradeable",
    ) or answers.asset not in ("btc", "broad_market"):
        veto = "No supported broad Bitcoin catalyst."
    elif answers.transmission in ("mixed", "unknown"):
        veto = "No clear Bitcoin transmission."
    elif answers.time_sensitivity not in ("immediate", "same_day"):
        veto = "Catalyst is not time-sensitive."
    expected = {
        "tariff_escalation": "risk_off",
        "tariff_deescalation": "risk_on",
        "crypto_policy_positive": "risk_on",
        "crypto_policy_negative": "risk_off",
    }.get(answers.event_type)
    if expected and answers.transmission != expected:
        veto = "Event classification and transmission conflict."
    return SocialMediaMarketSignal(
        is_tradeable=veto is None,
        event_type=answers.event_type,
        asset=answers.asset,
        direction="neutral"
        if veto
        else "up"
        if answers.transmission == "risk_on"
        else "down",
        confidence=confidence,
        novelty_score=1.0 if answers.concrete_new_action else 0.0,
        time_sensitivity=answers.time_sensitivity,
        risk_level=answers.risk_level,
        reasoning=reason,
        trade_veto_reason=veto,
    )
