"""Opt-in semantic October regressions. No trader is constructed."""

import json
import os
from pathlib import Path

import pytest

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.ai.jev_policy import decide
from app.config import AppConfig
from app.models import AnalysisAbstention, FEDDecisionImpact

pytestmark = [pytest.mark.live_jev, pytest.mark.live_llm, pytest.mark.asyncio]
DATA = Path(__file__).resolve().parents[1] / "testdata" / "fomc-oct-2026"
CASES = json.loads((DATA / "cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_live_october_fomc(case, mocker, record_property):
    if not os.getenv("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY required for opt-in live Jev test")
    payload = json.loads((DATA / f"{case['id']}.json").read_text())
    analyzer = FEDDecisionAnalyzer(str(DATA / "baseline.json"))
    run = mocker.spy(analyzer.agent, "run")
    try:
        result = await analyzer.analyze_content(payload["content"], payload["content-id"])
        run.assert_awaited_once()
        # A transport failure or an unrelated abstention must not pass this test.
        response = run.spy_return
        assert response is not None
        judgments = response.output
        for field, expected in case["required_live_judgments"].items():
            assert getattr(judgments, field) == expected, field
        semantic = decide(
            "fed", judgments, analyzer.expectations,
            {"confidence": dict.fromkeys(type(judgments).model_fields, 0.99)}, 0.85,
        )
        if case["expected"] == "abstain":
            assert isinstance(semantic, AnalysisAbstention)
        else:
            assert isinstance(semantic, FEDDecisionImpact)
            assert semantic.impact_on_bitcoin == case["expected"]
        actual = decide(
            "fed", judgments, analyzer.expectations,
            response.response.provider_details, AppConfig.JEV_CONFIDENCE_THRESHOLD,
        )
        assert result == actual
        record_property("outcome", "abstain" if isinstance(result, AnalysisAbstention)
                        else result.impact_on_bitcoin)
        record_property("provider_confidence", json.dumps(response.response.provider_details))
        if case["expected"] != "abstain" and isinstance(result, AnalysisAbstention):
            # Classification success is separate from production trade readiness.
            assert result.reason == "A required answer is below the Jev confidence threshold."
    finally:
        await analyzer.aclose()
