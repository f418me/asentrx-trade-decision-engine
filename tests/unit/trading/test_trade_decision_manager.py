import pytest
from unittest.mock import MagicMock

from app.config import AppConfig
from app.models import CPIReportImpact, FEDDecisionImpact, NFPReportImpact
from app.trading.trade_decision_manager import TradeDecisionManager


@pytest.fixture
def mock_trader():
    return MagicMock()


@pytest.fixture
def mock_slack_notifier():
    return MagicMock()


@pytest.fixture
def decision_manager(mock_trader, mock_slack_notifier):
    return TradeDecisionManager(trader=mock_trader, slack_notifier=mock_slack_notifier)


@pytest.mark.parametrize("impact, confidence, expected_amount, expected_leverage, description", [
    ("positive", AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + 0.01, AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "High-Confidence FED POSITIVE"),
    ("positive", (AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + AppConfig.CONFIDENCE_THRESHOLD_FED_MED) / 2, AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, AppConfig.LEVERAGE_FED_BUY_MED_CONF, "Medium-Confidence FED POSITIVE"),
    ("negative", AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + 0.01, AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "High-Confidence FED NEGATIVE"),
    ("negative", (AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + AppConfig.CONFIDENCE_THRESHOLD_FED_MED) / 2, AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "Medium-Confidence FED NEGATIVE"),
])
def test_execute_trade_for_fed_decision_triggers_correct_trades(decision_manager, mock_trader, mock_slack_notifier, mocker, impact, confidence, expected_amount, expected_leverage, description):
    decision_manager.PROD_EXECUTION = True
    mocker.patch.object(AppConfig, 'SLACK_NOTIFICATIONS_ENABLED', True)

    analysis_result = FEDDecisionImpact(
        impact_on_bitcoin=impact,
        confidence=confidence,
        reasoning="Test reasoning",
        actual_fed_decision_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-fed-123")

    mock_trader.execute_order.assert_called_once()
    call_kwargs = mock_trader.execute_order.call_args.kwargs
    assert call_kwargs['symbol'] == AppConfig.TRADE_SYMBOL
    assert call_kwargs['amount'] == expected_amount
    assert call_kwargs['leverage'] == expected_leverage
    assert call_kwargs['limit_offset_percentage'] is not None
    mock_slack_notifier.enqueue_message.assert_called_once()
    notification_body = mock_slack_notifier.enqueue_message.call_args.args[0]
    assert description in notification_body


@pytest.mark.parametrize("impact, confidence, expected_amount, expected_leverage, description", [
    ("positive", AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + 0.01, AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "High-Confidence NFP POSITIVE"),
    ("positive", (AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + AppConfig.CONFIDENCE_THRESHOLD_FED_MED) / 2, AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, AppConfig.LEVERAGE_FED_BUY_MED_CONF, "Medium-Confidence NFP POSITIVE"),
    ("negative", AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + 0.01, AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "High-Confidence NFP NEGATIVE"),
    ("negative", (AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + AppConfig.CONFIDENCE_THRESHOLD_FED_MED) / 2, AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "Medium-Confidence NFP NEGATIVE"),
])
def test_execute_trade_for_nfp_triggers_correct_trades(decision_manager, mock_trader, mock_slack_notifier, mocker, impact, confidence, expected_amount, expected_leverage, description):
    decision_manager.PROD_EXECUTION = True
    mocker.patch.object(AppConfig, 'SLACK_NOTIFICATIONS_ENABLED', True)

    analysis_result = NFPReportImpact(
        impact_on_bitcoin=impact,
        confidence=confidence,
        reasoning="Test reasoning",
        actual_report_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-nfp-123")

    mock_trader.execute_order.assert_called_once()
    call_kwargs = mock_trader.execute_order.call_args.kwargs
    assert call_kwargs['symbol'] == AppConfig.TRADE_SYMBOL
    assert call_kwargs['amount'] == expected_amount
    assert call_kwargs['leverage'] == expected_leverage
    assert call_kwargs['limit_offset_percentage'] is not None
    mock_slack_notifier.enqueue_message.assert_called_once()
    notification_body = mock_slack_notifier.enqueue_message.call_args.args[0]
    assert description in notification_body


@pytest.mark.parametrize("impact, confidence, expected_amount, expected_leverage, description", [
    ("positive", AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + 0.01, AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, AppConfig.LEVERAGE_FED_BUY_HIGH_CONF, "High-Confidence CPI POSITIVE"),
    ("positive", (AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + AppConfig.CONFIDENCE_THRESHOLD_FED_MED) / 2, AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, AppConfig.LEVERAGE_FED_BUY_MED_CONF, "Medium-Confidence CPI POSITIVE"),
    ("negative", AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + 0.01, AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF, "High-Confidence CPI NEGATIVE"),
    ("negative", (AppConfig.CONFIDENCE_THRESHOLD_FED_HIGH + AppConfig.CONFIDENCE_THRESHOLD_FED_MED) / 2, AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, AppConfig.LEVERAGE_FED_SHORT_MED_CONF, "Medium-Confidence CPI NEGATIVE"),
])
def test_execute_trade_for_cpi_triggers_correct_trades(decision_manager, mock_trader, mock_slack_notifier, mocker, impact, confidence, expected_amount, expected_leverage, description):
    decision_manager.PROD_EXECUTION = True
    mocker.patch.object(AppConfig, 'SLACK_NOTIFICATIONS_ENABLED', True)

    analysis_result = CPIReportImpact(
        impact_on_bitcoin=impact,
        confidence=confidence,
        reasoning="Test reasoning",
        actual_report_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-cpi-123")

    mock_trader.execute_order.assert_called_once()
    call_kwargs = mock_trader.execute_order.call_args.kwargs
    assert call_kwargs['symbol'] == AppConfig.TRADE_SYMBOL
    assert call_kwargs['amount'] == expected_amount
    assert call_kwargs['leverage'] == expected_leverage
    assert call_kwargs['limit_offset_percentage'] is not None
    mock_slack_notifier.enqueue_message.assert_called_once()
    notification_body = mock_slack_notifier.enqueue_message.call_args.args[0]
    assert description in notification_body


def test_execute_trade_does_nothing_for_neutral_impact(decision_manager, mock_trader):
    analysis_result = FEDDecisionImpact(
        impact_on_bitcoin="neutral",
        confidence=0.99,
        reasoning="Test neutral",
        actual_fed_decision_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-neutral-fed-123")
    mock_trader.execute_order.assert_not_called()
    decision_manager.slack_notifier.enqueue_message.assert_not_called()


@pytest.mark.parametrize("production,order_result,raises,status", [
    (False, None, False, "Simulated"),
    (True, True, False, "Submitted"),
    (True, None, False, "Failed"),
    (True, None, True, "Failed"),
])
def test_slack_reports_order_status(decision_manager, mock_trader, mock_slack_notifier,
                                    mocker, production, order_result, raises, status):
    mocker.patch.object(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    decision_manager.PROD_EXECUTION = production
    mock_trader.execute_order.return_value = order_result
    if raises:
        mock_trader.execute_order.side_effect = RuntimeError("Order rejected")
    result = FEDDecisionImpact(impact_on_bitcoin="positive", confidence=0.99,
                               reasoning="Test", actual_fed_decision_summary="Test")
    decision_manager.execute_trade_from_analysis(result, "event-status")
    call = mock_slack_notifier.enqueue_message.call_args
    assert f"Status: {status}" in call.args[0]
    assert ("[LIVE]" if production else "[DRY RUN]") in call.args[0]
    assert call.kwargs["content_id"] == "event-status"
    assert mock_trader.execute_order.call_count == int(production)


def test_execute_trade_does_nothing_for_neutral_nfp_impact(decision_manager, mock_trader):
    analysis_result = NFPReportImpact(
        impact_on_bitcoin="neutral",
        confidence=0.99,
        reasoning="Test neutral",
        actual_report_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-neutral-nfp-123")
    mock_trader.execute_order.assert_not_called()


def test_execute_trade_does_nothing_for_neutral_cpi_impact(decision_manager, mock_trader):
    analysis_result = CPIReportImpact(
        impact_on_bitcoin="neutral",
        confidence=0.99,
        reasoning="Test neutral",
        actual_report_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-neutral-cpi-123")
    mock_trader.execute_order.assert_not_called()


def test_execute_trade_does_nothing_for_low_confidence(decision_manager, mock_trader):
    low_confidence = AppConfig.CONFIDENCE_THRESHOLD_FED_MED - 0.01
    analysis_result = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=low_confidence,
        reasoning="Test low confidence",
        actual_fed_decision_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-low-conf-fed-123")
    mock_trader.execute_order.assert_not_called()


def test_execute_trade_does_nothing_for_low_confidence_nfp(decision_manager, mock_trader):
    low_confidence = AppConfig.CONFIDENCE_THRESHOLD_FED_MED - 0.01
    analysis_result = NFPReportImpact(
        impact_on_bitcoin="positive",
        confidence=low_confidence,
        reasoning="Test low confidence",
        actual_report_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-low-conf-nfp-123")
    mock_trader.execute_order.assert_not_called()


def test_execute_trade_does_nothing_for_low_confidence_cpi(decision_manager, mock_trader):
    low_confidence = AppConfig.CONFIDENCE_THRESHOLD_FED_MED - 0.01
    analysis_result = CPIReportImpact(
        impact_on_bitcoin="positive",
        confidence=low_confidence,
        reasoning="Test low confidence",
        actual_report_summary="Test summary"
    )
    decision_manager.execute_trade_from_analysis(analysis_result, "test-low-conf-cpi-123")
    mock_trader.execute_order.assert_not_called()
