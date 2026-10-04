import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.ai.agents.cpi_decision_agent import CPIDecisionAnalyzer
from app.ai.agents.nfp_decision_agent import NFPDecisionAnalyzer
from app.ai.agents.social_media_agent import SocialMediaPostAnalyzer
from app.ai.jev_schemas import FEDJudgments, CPIJudgments, NFPJudgments, SocialJudgments
from app.config import AppConfig
from app.models import AnalysisAbstention

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

CASES = [
    (
        FEDDecisionAnalyzer,
        FEDJudgments(
            is_fresh_release=True,
            actual_change_bp=0,
            actual_narrative="dovish",
            guidance_vs_baseline="more_dovish",
        ),
    ),
    (
        CPIDecisionAnalyzer,
        CPIJudgments(
            is_fresh_release=True,
            headline_mom="below",
            headline_yoy="below",
            core_mom="below",
            core_yoy="below",
        ),
    ),
    (
        NFPDecisionAnalyzer,
        NFPJudgments(
            is_fresh_release=True,
            payrolls="below",
            unemployment="above",
            wages_mom="below",
            growth_scare="no",
        ),
    ),
    (
        SocialMediaPostAnalyzer,
        SocialJudgments(
            event_type="crypto_policy_positive",
            asset="btc",
            concrete_new_action=True,
            transmission="risk_on",
            time_sensitivity="immediate",
            risk_level="medium",
        ),
    ),
]


@pytest.mark.parametrize("cls,answers", CASES)
async def test_single_call_and_audit(cls, answers, mocker, monkeypatch):
    monkeypatch.setattr(AppConfig, "JEV_CONFIDENCE_THRESHOLD", 0.85)
    details = {"confidence": dict.fromkeys(type(answers).model_fields, 0.99)}
    agent = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(
                output=answers,
                response=SimpleNamespace(
                    provider_details=details, model_name="jev-test"
                ),
            )
        )
    )
    mocker.patch.object(cls, "_initialize_agent", return_value=agent)
    log = mocker.patch("app.ai.jev_analyzer.logfire_info")
    analyzer = cls()
    result = await analyzer.analyze_content("Announcement text", "case-123")
    assert not isinstance(result, AnalysisAbstention)
    assert result.confidence == 0.99
    agent.run.assert_awaited_once()
    state = json.loads(agent.run.call_args.args[0])
    assert state["announcement"] == "Announcement text"
    assert "case-123" not in agent.run.call_args.args[0]
    assert "notes" not in (state["pre_announcement_expectations"] or {})
    audit = log.call_args.kwargs
    assert audit["content_id"] == "case-123"
    assert audit["elapsed_ms"] >= 0
    assert audit["provider_details"] == details
    assert audit["decision"] == result.model_dump()


@pytest.mark.parametrize("cls,answers", CASES)
async def test_missing_confidence_never_creates_signal(cls, answers, mocker):
    agent = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(
                output=answers,
                response=SimpleNamespace(provider_details=None, model_name="jev-test"),
            )
        )
    )
    mocker.patch.object(cls, "_initialize_agent", return_value=agent)
    assert isinstance(await cls().analyze_content("Announcement"), AnalysisAbstention)


@pytest.mark.parametrize("cls,answers", CASES)
async def test_provider_failure_no_retry(cls, answers, mocker):
    agent = SimpleNamespace(
        run=AsyncMock(side_effect=RuntimeError("provider unavailable"))
    )
    mocker.patch.object(cls, "_initialize_agent", return_value=agent)
    result = await cls().analyze_content("Announcement")
    assert isinstance(result, cls.failure_type)
    agent.run.assert_awaited_once()


async def test_timeout_cancels_request(mocker, monkeypatch):
    async def slow(_):
        await asyncio.sleep(10)

    agent = SimpleNamespace(run=AsyncMock(side_effect=slow))
    mocker.patch.object(FEDDecisionAnalyzer, "_initialize_agent", return_value=agent)
    monkeypatch.setattr(AppConfig, "JEV_TIMEOUT_SECONDS", 0.01)
    result = await FEDDecisionAnalyzer().analyze_content("Announcement")
    assert "TimeoutError" in result.error_message
    agent.run.assert_awaited_once()
