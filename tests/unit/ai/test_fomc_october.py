"""Offline policy/contract regressions, not tests of Jev's text understanding."""

import json
from pathlib import Path

import pytest

from app.ai.jev_policy import decide
from app.ai.jev_schemas import FEDJudgments
from app.models import AnalysisAbstention, FEDDecisionImpact, FEDExpectation, WebMonitorPayload

pytestmark = pytest.mark.unit
DATA = Path(__file__).resolve().parents[2] / "testdata" / "fomc-oct-2026"
CASES = json.loads((DATA / "cases.json").read_text())


def baseline():
    return FEDExpectation.model_validate_json((DATA / "baseline.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_october_contract_and_policy(case):
    payload = WebMonitorPayload.model_validate_json(
        (DATA / f"{case['id']}.json").read_text()
    )
    assert payload.content_id == f"synthetic-fomc-20261028-{case['id']}"
    assert payload.content.strip()
    answers = FEDJudgments.model_validate(case["judgments"])
    details = {"confidence": dict.fromkeys(FEDJudgments.model_fields, 0.99)}
    result = decide("fed", answers, baseline(), details, 0.85)
    if case["expected"] == "abstain":
        assert isinstance(result, AnalysisAbstention)
    else:
        assert isinstance(result, FEDDecisionImpact)
        assert result.impact_on_bitcoin == case["expected"]
        assert result.confidence == 0.99


@pytest.mark.parametrize("field", ["is_fresh_release", "actual_change_bp", "guidance_vs_baseline"])
@pytest.mark.parametrize("value", [None, 0.84])
def test_october_hold_requires_all_relevant_confidence(field, value):
    answers = FEDJudgments.model_validate(CASES[0]["judgments"])
    details = {"confidence": {**dict.fromkeys(FEDJudgments.model_fields, 0.99), field: value}}
    assert isinstance(decide("fed", answers, baseline(), details, 0.85), AnalysisAbstention)


def test_october_rate_surprise_takes_priority_over_dovish_guidance():
    answers = FEDJudgments(
        is_fresh_release=True, actual_change_bp=25,
        actual_narrative="dovish", guidance_vs_baseline="more_dovish",
    )
    details = {"confidence": {"is_fresh_release": 0.99, "actual_change_bp": 0.85}}
    result = decide("fed", answers, baseline(), details, 0.85)
    assert isinstance(result, FEDDecisionImpact)
    assert result.impact_on_bitcoin == "negative"
    assert result.confidence == 0.85
