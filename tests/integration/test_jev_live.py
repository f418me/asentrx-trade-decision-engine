"""Opt-in Jev regression tests: no trader or exchange connection is constructed."""

import json
import math
import os
from pathlib import Path

import pytest

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.models import AnalysisAbstention, FEDDecisionImpact
from app.config import AppConfig

# Keep the alias so existing `-m 'not live_llm'` commands remain offline.
pytestmark = [pytest.mark.live_jev, pytest.mark.live_llm, pytest.mark.asyncio]
FIXTURES = Path(__file__).resolve().parents[1] / "testdata" / "fomc-sept-2026"


@pytest.mark.parametrize(
    "case,expected",
    [
        ("expected-25bp-hawkish-neutral", "neutral"),
        ("surprise-hold-dovish-positive", "positive"),
        ("hawkish-50bp-negative", "negative"),
        ("dovish-hike-positive", "positive"),
        ("preview-irrelevant", "abstain"),
    ],
)
async def test_live_fomc(case, expected, tmp_path, mocker):
    if not os.getenv("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY required for opt-in live Jev test")
    # Freeze the synthetic September baseline independently of production updates.
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "expected_interest_rate_change_type": "increase",
                "expected_interest_rate_change_amount": "+25bp",
                "expected_narrative": "hawkish",
            }
        )
    )
    payload = json.loads((FIXTURES / f"fomc-2026-09-16-{case}.json").read_text())
    analyzer = FEDDecisionAnalyzer(str(baseline))
    run = mocker.spy(analyzer.agent, "run")
    try:
        result = await analyzer.analyze_content(payload["content"], case)
        run.assert_awaited_once()
        if expected == "neutral":
            # Inspect the same live response independently of the policy gate.
            # A wrong classification or a provider failure must not pass as no trade.
            response = run.spy_return
            judgments = response.output
            assert judgments.is_fresh_release is True
            assert judgments.actual_change_bp == 25
            assert judgments.actual_narrative == "hawkish"
            assert judgments.guidance_vs_baseline == "in_line"
            if isinstance(result, AnalysisAbstention):
                assert result.source == "fed"
                assert result.reason == "A required answer is below the Jev confidence threshold."
                confidence = response.response.provider_details["confidence"]
                required = [confidence[field] for field in (
                    "is_fresh_release", "actual_change_bp", "guidance_vs_baseline",
                )]
                assert all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 for value in required)
                assert min(required) < AppConfig.JEV_CONFIDENCE_THRESHOLD
            else:
                assert isinstance(result, FEDDecisionImpact), result
                assert result.impact_on_bitcoin == "neutral"
        elif expected == "abstain":
            assert isinstance(result, AnalysisAbstention)
        else:
            assert isinstance(result, FEDDecisionImpact), result
            assert result.impact_on_bitcoin == expected
    finally:
        await analyzer.aclose()
