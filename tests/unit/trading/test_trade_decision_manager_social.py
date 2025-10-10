import pytest
from unittest.mock import MagicMock
from app.trading.trade_decision_manager import TradeDecisionManager
from app.models import SocialMediaAnalysisOutput
from app.config import AppConfig

@pytest.fixture
def mock_trader():
    return MagicMock()

@pytest.fixture
def mock_sms_notifier():
    return MagicMock()

def test_execute_trade_from_social_media_bitcoin_high_confidence(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    mocker.patch.object(AppConfig, 'TS_ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF', 0.02)
    mocker.patch.object(AppConfig, 'TS_LEVERAGE_BITCOIN_BUY_HIGH_CONF', 25)
    
    # Re-initialize manager to pick up patched config
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)

    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="bitcoin",
        price_direction="up",
        price_confidence=0.99 # Above default high threshold
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-1")

    # Assert
    mock_trader.execute_order.assert_called_once()
    call_kwargs = mock_trader.execute_order.call_args.kwargs
    assert call_kwargs['amount'] == 0.02
    assert call_kwargs['leverage'] == 25

def test_execute_trade_from_social_media_tariffs_med_confidence(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    mocker.patch.object(AppConfig, 'TS_ORDER_AMOUNT_SHORT_MED_CONF', -0.05)
    mocker.patch.object(AppConfig, 'TS_LEVERAGE_SHORT_MED_CONF', 8)
    mocker.patch.object(AppConfig, 'TS_CONFIDENCE_THRESHOLD_MED', 0.85)

    # Re-initialize manager to pick up patched config
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)

    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="tariffs",
        price_direction="down",
        price_confidence=0.86 # Above medium threshold
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-2")

    # Assert
    mock_trader.execute_order.assert_called_once()
    call_kwargs = mock_trader.execute_order.call_args.kwargs
    assert call_kwargs['amount'] == -0.05
    assert call_kwargs['leverage'] == 8

def test_no_trade_if_confidence_too_low(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)
    
    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="market",
        price_direction="up",
        price_confidence=0.70 # Below default medium threshold of 0.9
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-3")

    # Assert
    mock_trader.execute_order.assert_not_called()

def test_no_trade_for_irrelevant_topic(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)
    
    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="others",
        price_direction="up",
        price_confidence=0.99
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-4")

    # Assert
    mock_trader.execute_order.assert_not_called()