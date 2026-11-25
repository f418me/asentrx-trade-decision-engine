from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.ai.agents.pce_decision_agent import PCEDecisionAnalyzer
from app.ai.jev_policy import decide
from app.ai.jev_schemas import PCEJudgments
from app.config import AppConfig
from app.models import AnalysisAbstention, FailedPCEAnalysis, PCEReportImpact
from app.trading.trade_decision_manager import TradeDecisionManager

pytestmark = pytest.mark.unit


def answers(**overrides):
    return PCEJudgments(**dict(dict(is_fresh_release=True, matches_report_month=True,
        headline_mom="in_line", headline_yoy="in_line", core_mom="in_line",
        core_yoy="in_line"), **overrides))


@pytest.mark.parametrize("changes,expected", [
    ({}, "neutral"), ({"core_mom": "below"}, "positive"),
    ({"core_mom": "above"}, "negative"), ({"core_yoy": "above"}, "neutral"),
    ({"headline_mom": "above"}, "neutral"),
    ({"core_mom": "below", "core_yoy": "above"}, "abstain"),
    ({"core_mom": "above", "headline_mom": "below"}, "abstain"),
    ({"matches_report_month": False}, "abstain"),
    ({"is_fresh_release": False}, "abstain"),
    ({"core_mom": "unknown"}, "abstain"),
])
def test_pce_policy(changes, expected):
    result = decide("pce", answers(**changes), SimpleNamespace(release_at=datetime.now(timezone.utc), window_seconds=300),
                    {"confidence": dict.fromkeys(PCEJudgments.model_fields, .99)}, .85)
    if expected == "abstain":
        assert isinstance(result, AnalysisAbstention)
    else:
        assert isinstance(result, PCEReportImpact)
        assert result.impact_on_bitcoin == expected


@pytest.mark.parametrize("confidence", [None, {}, {"core_mom": .99},
    dict.fromkeys(PCEJudgments.model_fields, .5),
    dict.fromkeys(PCEJudgments.model_fields, float("nan"))])
def test_pce_confidence_fails_closed(confidence):
    assert isinstance(decide("pce", answers(core_mom="above"), None,
                              {"confidence": confidence}, .85), AnalysisAbstention)


@pytest.fixture
def analyzer(mocker):
    agent = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(
        output=answers(core_mom="below"), response=SimpleNamespace(
            model_name="jev-test", provider_details={
                "confidence": dict.fromkeys(PCEJudgments.model_fields, .99)}))))
    mocker.patch.object(PCEDecisionAnalyzer, "_initialize_agent", return_value=agent)
    return PCEDecisionAnalyzer()


@pytest.mark.parametrize("offset,expected", [(-1, False), (0, True), (299, True), (300, False)])
def test_release_window(analyzer, mocker, offset, expected):
    clock = mocker.patch("app.ai.agents.pce_decision_agent.datetime")
    clock.now.return_value = analyzer.expectations.release_at + timedelta(seconds=offset)
    assert analyzer.in_release_window() is expected


@pytest.mark.asyncio
async def test_single_request_and_window_expiry(analyzer, mocker):
    window = mocker.patch.object(analyzer, "in_release_window", return_value=True)
    result = await analyzer.analyze_content("PCE release", "pce-test")
    assert result.impact_on_bitcoin == "positive"
    analyzer.agent.run.assert_awaited_once()
    assert "2026-10" in analyzer.agent.run.call_args.args[0]
    window.side_effect = [True, False]
    assert isinstance(await analyzer.analyze_content("PCE release"), AnalysisAbstention)


@pytest.mark.asyncio
async def test_outside_window_never_calls_provider(analyzer, mocker):
    mocker.patch.object(analyzer, "in_release_window", return_value=False)
    assert isinstance(await analyzer.analyze_content("PCE release"), AnalysisAbstention)
    analyzer.agent.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_failure(analyzer, mocker):
    mocker.patch.object(analyzer, "in_release_window", return_value=True)
    analyzer.agent.run.side_effect = RuntimeError("unavailable")
    assert isinstance(await analyzer.analyze_content("PCE release"), FailedPCEAnalysis)
    analyzer.agent.run.assert_awaited_once()


@pytest.mark.parametrize("direction,confidence,tier", [
    ("positive", .99, "HIGH"), ("negative", .92, "MED"),
    ("negative", .99, "HIGH"), ("positive", .92, "MED"),
    ("positive", .89, None), ("neutral", .99, None), ("positive", float("nan"), None)])
def test_separate_pce_sizing(monkeypatch, direction, confidence, tier):
    monkeypatch.setattr(AppConfig, "PROD_EXECUTION", True)
    monkeypatch.setattr(AppConfig, "PCE_CONFIDENCE_THRESHOLD_HIGH", .95)
    monkeypatch.setattr(AppConfig, "PCE_CONFIDENCE_THRESHOLD_MED", .90)
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    trader, slack = Mock(), Mock()
    manager = TradeDecisionManager(trader, slack)
    result = PCEReportImpact(expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                            impact_on_bitcoin=direction, confidence=confidence,
                            reasoning="test", actual_report_summary="test")
    manager.execute_trade_from_analysis(result, "pce-test")
    if tier is None:
        trader.execute_order.assert_not_called()
        slack.enqueue_message.assert_not_called()
    else:
        call = trader.execute_order.call_args.kwargs
        side = "BUY" if direction == "positive" else "SHORT"
        assert call["amount"] == getattr(AppConfig, f"PCE_ORDER_AMOUNT_{side}_{tier}_CONF")
        assert call["leverage"] == getattr(AppConfig, f"PCE_LEVERAGE_{tier}")
        assert call["limit_offset_percentage"] == AppConfig.PCE_LIMIT_OFFSET
        slack.enqueue_message.assert_called_once()


@pytest.mark.parametrize("key,value", [
    ("PCE_ORDER_AMOUNT_BUY_HIGH_CONF", -1),
    ("PCE_ORDER_AMOUNT_BUY_HIGH_CONF", float("inf")),
    ("PCE_LEVERAGE_HIGH", 0), ("PCE_LIMIT_OFFSET", float("nan")),
    ("PCE_CONFIDENCE_THRESHOLD_MED", 1.1)])
def test_invalid_pce_config_fails_closed(monkeypatch, key, value):
    monkeypatch.setattr(AppConfig, key, value)
    manager = TradeDecisionManager(Mock(), Mock())
    result = PCEReportImpact(expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                            impact_on_bitcoin="positive", confidence=.99,
                            reasoning="test", actual_report_summary="test")
    manager.execute_trade_from_analysis(result, "pce-invalid")
    manager.trader.execute_order.assert_not_called()
