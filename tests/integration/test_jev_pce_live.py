"""Opt-in synthetic PCE semantics; no trader or notification endpoint is used."""
import json
import os
from pathlib import Path

import pytest

from app.ai.agents.pce_decision_agent import PCEDecisionAnalyzer
from app.ai.jev_policy import decide
from app.models import AnalysisAbstention, PCEReportImpact

pytestmark = [pytest.mark.live_jev, pytest.mark.live_llm, pytest.mark.asyncio]
DATA = Path(__file__).resolve().parents[1] / "testdata" / "pce-nov-2026"
CASES = json.loads((DATA / "cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_live_pce(case, mocker, record_property):
    if not os.getenv("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY required")
    analyzer = PCEDecisionAnalyzer(str(DATA / "baseline.json"))
    # Test semantic classification on any date; production keeps its time gate.
    mocker.patch.object(analyzer, "in_release_window", return_value=True)
    run = mocker.spy(analyzer.agent, "run")
    try:
        result = await analyzer.analyze_content(case["content"], "synthetic-pce-" + case["id"])
        run.assert_awaited_once()
        response = run.spy_return
        assert response is not None, "Provider failed"
        for field, expected in case["judgments"].items():
            assert getattr(response.output, field) == expected
        semantic = decide("pce", response.output, analyzer.expectations,
            {"confidence": dict.fromkeys(type(response.output).model_fields, .99)}, .85)
        if case["expected"] == "abstain":
            assert isinstance(semantic, AnalysisAbstention)
            assert isinstance(result, AnalysisAbstention)
        else:
            assert isinstance(semantic, PCEReportImpact)
            assert semantic.impact_on_bitcoin == case["expected"]
            if isinstance(result, AnalysisAbstention):
                assert result.reason == "A required answer is below the Jev confidence threshold."
            else:
                assert isinstance(result, PCEReportImpact)
                assert result.impact_on_bitcoin == case["expected"]
        record_property("provider_details", json.dumps(response.response.provider_details))
        record_property("decision", result.model_dump_json())
    finally:
        await analyzer.aclose()
