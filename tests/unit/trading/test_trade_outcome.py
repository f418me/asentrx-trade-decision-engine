from unittest.mock import MagicMock

import pytest

from app.config import AppConfig
from app.models import AnalysisAbstention, FEDDecisionImpact
from app.trading.trade_decision_manager import TradeDecisionManager
from app.utils import observability

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("direction,confidence,production,success,expected,code", [
    ("neutral", 0.99, True, True, "no_trade", "neutral_signal"),
    ("positive", 0.1, True, True, "no_trade", "confidence_below_threshold"),
    ("positive", 0.99, False, True, "dry_run", "production_disabled"),
    ("positive", 0.99, True, True, "submitted", "signal_accepted"),
    ("negative", 0.99, True, False, "submission_failed", "execution_failed"),
])
def test_outcome_summary(mocker, direction, confidence, production, success, expected, code):
    mocker.patch.object(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", False)
    trader = MagicMock()
    trader.execute_order.return_value = success
    manager = TradeDecisionManager(trader, None)
    manager.PROD_EXECUTION = production
    event = mocker.patch("app.trading.trade_decision_manager.trade_outcome")
    result = FEDDecisionImpact(impact_on_bitcoin=direction, confidence=confidence,
                               reasoning="Rate matches baseline; guidance: in_line.",
                               actual_fed_decision_summary="Test")
    manager.execute_trade_from_analysis(result, "monetary-test")
    event.assert_called_once()
    fields = event.call_args.kwargs
    assert fields["content_id"] == "monetary-test"
    assert fields["outcome"] == expected
    assert fields["reason_code"] == code
    assert fields["analysis_reasoning"] == result.reasoning
    assert fields["confidence"] == confidence
    assert fields["order_attempted"] == (expected in {"submitted", "submission_failed"})


def test_abstention_has_content_id_and_field_confidence(test_app_client, mocker):
    client, mocks = test_app_client
    mocks["fed_analyzer"].analyze_content.return_value = AnalysisAbstention(
        source="fed", reason="A required answer is below the Jev confidence threshold.",
        confidence_by_field={"guidance_vs_baseline": 0.22})
    event = mocker.patch("app.main.trade_outcome")
    response = client.post("/notify/web-monitor", json={
        "uuid": "request-123", "type": "web-monitor", "ip": "test",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary-test.htm",
        "content-id": "monetary-test", "content": "FOMC statement",
    })
    assert response.status_code == 200
    event.assert_called_once()
    fields = event.call_args.kwargs
    assert fields["uuid"] == "request-123"
    assert fields["content_id"] == "monetary-test"
    assert fields["confidence_by_field"]["guidance_vs_baseline"] == 0.22
    assert fields["reason_code"] == "analysis_abstained"
    mocks["trade_manager"].execute_trade_from_analysis.assert_not_called()


def test_outcome_export_failure_is_nonfatal(mocker):
    mocker.patch.object(observability, "logfire_info", side_effect=RuntimeError("offline"))
    observability.trade_outcome(content_id="test", outcome="no_trade",
                                reason_code="test", reason="Test")
