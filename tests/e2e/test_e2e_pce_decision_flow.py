from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models import AnalysisAbstention, FailedPCEAnalysis, PCEExpectation, PCEReportImpact
from pathlib import Path
from datetime import datetime, timedelta, timezone
from app.ai.agents.pce_decision_agent import PCEDecisionAnalyzer
from app.ai.jev_schemas import PCEJudgments
from app.config import AppConfig
from app.trading.trade_decision_manager import TradeDecisionManager

pytestmark = pytest.mark.e2e
URL = "https://www.bea.gov/news/2026/personal-income-and-outlays-october-2026"


@pytest.fixture
def pce_client(test_app_client):
    client, mocks = test_app_client
    analyzer = SimpleNamespace(
        expectations=PCEExpectation.model_validate_json(Path("app/pce_expectations.json").read_text()),
        in_release_window=Mock(return_value=True),
        analyze_content=AsyncMock(return_value=PCEReportImpact(expires_at=datetime.now(timezone.utc) + timedelta(minutes=5), impact_on_bitcoin="negative",
            confidence=.99, reasoning="Hot core", actual_report_summary="Hot core")))
    client.app.state.pce_decision_analyzer = analyzer
    return client, mocks, analyzer


def payload(**changes):
    return dict(dict(type="web-monitor", source="pce", url=URL, content="PCE release",
                     ip="127.0.0.1", **{"content-id": "bea-pce-2026-10"}), **changes)


def test_routing_and_dedup(pce_client):
    client, mocks, analyzer = pce_client
    assert client.post("/notify/web-monitor", json=payload()).json()["status"] == "success"
    assert client.post("/notify/web-monitor", json=payload(**{"content-id": "different"})).status_code == 409
    analyzer.analyze_content.assert_awaited_once()
    mocks["trade_manager"].execute_trade_from_analysis.assert_called_once()
    mocks["fed_analyzer"].analyze_content.assert_not_awaited()
    mocks["cpi_analyzer"].analyze_content.assert_not_awaited()


@pytest.mark.parametrize("url", [URL.replace("october", "september"),
    "https://www.bea.gov/news/2026/gdp-second-estimate", URL.replace("www.bea.gov", "example.com")])
def test_wrong_release_rejected(pce_client, url, monkeypatch):
    client, mocks, analyzer = pce_client
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    assert client.post("/notify/web-monitor", json=payload(url=url)).json()["status"] == "success_no_action"
    analyzer.analyze_content.assert_not_awaited()
    mocks["trade_manager"].execute_trade_from_analysis.assert_not_called()
    mocks["slack_notifier"].enqueue_abstention.assert_not_called()


def test_early_notification_does_not_consume_event(pce_client, monkeypatch):
    client, mocks, analyzer = pce_client
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    analyzer.in_release_window.return_value = False
    assert client.post("/notify/web-monitor", json=payload()).json()["status"] == "success_no_action"
    mocks["slack_notifier"].enqueue_abstention.assert_not_called()
    analyzer.in_release_window.return_value = True
    assert client.post("/notify/web-monitor", json=payload()).json()["status"] == "success"


@pytest.mark.parametrize("result,status", [
    (AnalysisAbstention(source="pce", reason="Low confidence"), "success_no_action"),
    (FailedPCEAnalysis(error_message="Provider failed"), "success_analysis_failed")])
def test_pce_failure_never_reaches_trader(pce_client, result, status):
    client, mocks, analyzer = pce_client
    analyzer.analyze_content.return_value = result
    assert client.post("/notify/web-monitor", json=payload()).json()["status"] == status
    mocks["trade_manager"].execute_trade_from_analysis.assert_not_called()


@pytest.mark.parametrize("mode", [True, False])
def test_pce_full_mocked_flow(test_app_client, mocker, monkeypatch, mode):
    client, _ = test_app_client
    monkeypatch.setattr(AppConfig, "PROD_EXECUTION", mode)
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    judgments = PCEJudgments(is_fresh_release=True, matches_report_month=True,
        headline_mom="above", headline_yoy="above", core_mom="above", core_yoy="above")
    agent = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(output=judgments,
        response=SimpleNamespace(model_name="test", provider_details={
            "confidence": dict.fromkeys(PCEJudgments.model_fields, .99)}))))
    mocker.patch.object(PCEDecisionAnalyzer, "_initialize_agent", return_value=agent)
    analyzer = PCEDecisionAnalyzer()
    analyzer.expectations.release_at = datetime.now(timezone.utc)
    mocker.patch.object(analyzer, "in_release_window", return_value=True)
    client.app.state.pce_decision_analyzer = analyzer
    trader, slack = Mock(), Mock()
    client.app.state.trade_decision_manager = TradeDecisionManager(trader, slack)
    response = client.post("/notify/web-monitor", json=payload())
    assert response.json()["status"] == "success"
    agent.run.assert_awaited_once()
    if mode:
        trader.execute_order.assert_called_once()
        assert trader.execute_order.call_args.kwargs["amount"] == AppConfig.PCE_ORDER_AMOUNT_SHORT_HIGH_CONF
    else:
        trader.execute_order.assert_not_called()
    slack.enqueue_message.assert_called_once()


def test_bea_source_cannot_bypass_time_gate(pce_client):
    client, mocks, analyzer = pce_client
    analyzer.in_release_window.return_value = False
    response = client.post("/notify/web-monitor", json=payload(source="cpi"))
    assert response.json()["status"] == "success_no_action"
    mocks["cpi_analyzer"].analyze_content.assert_not_awaited()
    mocks["trade_manager"].execute_trade_from_analysis.assert_not_called()


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("queue_fails", [True, False])
def test_pce_abstention_slack_without_trade_or_duplicate(pce_client, monkeypatch, mocker,
                                                       enabled, queue_fails):
    from app.utils.slack_notifier import SlackNotifier

    client, mocks, analyzer = pce_client
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", enabled)
    monkeypatch.setattr(AppConfig, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/CHANNEL/secret")
    notifier = SlackNotifier()
    enqueue = mocker.patch.object(notifier, "enqueue_message", return_value=True)
    if queue_fails:
        enqueue.side_effect = RuntimeError("queue failed")
    client.app.state.slack_notifier = notifier
    result = AnalysisAbstention(source="pce", reason="A required answer is below the Jev confidence threshold.",
        confidence_by_field={"is_fresh_release": .94, "matches_report_month": .96,
            "headline_mom": 1, "headline_yoy": 1, "core_mom": 1, "core_yoy": .83})
    analyzer.analyze_content.return_value = result
    try:
        response = client.post("/notify/web-monitor", json=payload())
        assert response.status_code == 200
        assert response.json() == {"status": "success_no_action", "message": result.reason}
        assert client.post("/notify/web-monitor", json=payload()).status_code == 409
        assert enqueue.call_count == int(enabled)
        if enabled:
            assert "core_yoy: 0.83" in enqueue.call_args.args[0]
        mocks["trade_manager"].execute_trade_from_analysis.assert_not_called()
    finally:
        notifier.close()
