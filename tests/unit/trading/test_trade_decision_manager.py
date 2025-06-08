# tests/unit/trading/test_trade_decision_manager.py

import pytest
from unittest.mock import MagicMock

from app.models import FEDDecisionImpact
from app.trading.trade_decision_manager import TradeDecisionManager
from app.config import AppConfig


@pytest.fixture
def mock_trader():
    """Creates a mock for the Trader class."""
    return MagicMock()


@pytest.fixture
def mock_sms_notifier():
    """Creates a mock for the SmsNotifier class."""
    return MagicMock()


@pytest.fixture
def decision_manager(mock_trader, mock_sms_notifier):
    """Initializes the TradeDecisionManager with mocks for each test."""
    return TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)


@pytest.mark.parametrize("impact, confidence, expected_amount, expected_leverage, description", [
    # Test cases for FED Decision trades
    ("positive", 0.97, AppConfig.ORDER_AMOUNT_FED_BUY_HIGH_CONF, AppConfig.LEVERAGE_FED_BUY_HIGH_CONF,
     "High-Confidence UP"),
    ("positive", 0.93, AppConfig.ORDER_AMOUNT_FED_BUY_MED_CONF, AppConfig.LEVERAGE_FED_BUY_MED_CONF,
     "Medium-Confidence UP"),
    ("negative", 0.98, AppConfig.ORDER_AMOUNT_FED_SHORT_HIGH_CONF, AppConfig.LEVERAGE_FED_SHORT_HIGH_CONF,
     "High-Confidence DOWN"),
    ("negative", 0.94, AppConfig.ORDER_AMOUNT_FED_SHORT_MED_CONF, AppConfig.LEVERAGE_FED_SHORT_MED_CONF,
     "Medium-Confidence DOWN"),
])
def test_execute_trade_for_fed_decision_triggers_correct_trades(
        decision_manager, mock_trader, mock_sms_notifier, mocker,
        impact, confidence, expected_amount, expected_leverage, description
):
    """
    Tests if correct trades are triggered for FED decisions based on confidence and direction.
    """
    # 1. Arrange
    # Temporarily set PROD_EXECUTION to True for this test to run the trade logic.
    decision_manager.PROD_EXECUTION = True
    # Temporarily patch AppConfig to enable SMS notifications for this test.
    mocker.patch.object(AppConfig, 'SMS_NOTIFICATIONS_ENABLED', True)

    analysis_result = FEDDecisionImpact(
        impact_on_bitcoin=impact,
        confidence=confidence,
        reasoning="Test reasoning",
        actual_fed_decision_summary="Test summary"
    )
    content_id = "test-fed-123"

    # 2. Act
    decision_manager.execute_trade_from_analysis(analysis_result, content_id)

    # 3. Assert
    # Was the trader's execute_order method called exactly once?
    mock_trader.execute_order.assert_called_once()

    # Extract the keyword arguments with which execute_order was called
    call_kwargs = mock_trader.execute_order.call_args.kwargs

    # Verify the arguments are correct
    assert call_kwargs['symbol'] == AppConfig.TRADE_SYMBOL
    assert call_kwargs['amount'] == expected_amount
    assert call_kwargs['leverage'] == expected_leverage
    assert call_kwargs['limit_offset_percentage'] is not None

    # Was an SMS sent?
    mock_sms_notifier.send_sms.assert_called_once()
    sms_body = mock_sms_notifier.send_sms.call_args.args[0]
    assert description in sms_body
    assert f"Amt: {expected_amount}" in sms_body


def test_execute_trade_does_nothing_for_neutral_impact(decision_manager, mock_trader):
    """Tests that no trade is triggered for a neutral impact."""
    # 1. Arrange
    analysis_result = FEDDecisionImpact(
        impact_on_bitcoin="neutral",
        confidence=0.99,
        reasoning="Test neutral",
        actual_fed_decision_summary="Test summary"
    )

    # 2. Act
    decision_manager.execute_trade_from_analysis(analysis_result, "test-neutral-123")

    # 3. Assert
    # execute_order must NOT have been called.
    mock_trader.execute_order.assert_not_called()


def test_execute_trade_does_nothing_for_low_confidence(decision_manager, mock_trader):
    """Tests that no trade is triggered for low confidence."""
    # 1. Arrange
    # Confidence is below the threshold for MED
    low_confidence = AppConfig.CONFIDENCE_THRESHOLD_FED_MED - 0.01
    analysis_result = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=low_confidence,
        reasoning="Test low confidence",
        actual_fed_decision_summary="Test summary"
    )

    # 2. Act
    decision_manager.execute_trade_from_analysis(analysis_result, "test-low-conf-123")

    # 3. Assert
    mock_trader.execute_order.assert_not_called()