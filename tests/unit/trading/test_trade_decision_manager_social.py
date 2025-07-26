
import pytest
from unittest.mock import MagicMock
from app.trading.trade_decision_manager import TradeDecisionManager
from app.models import SocialMediaAnalysisOutput

@pytest.fixture
def mock_trader():
    return MagicMock()

@pytest.fixture
def mock_sms_notifier():
    return MagicMock()

@pytest.fixture
def decision_manager(mock_trader, mock_sms_notifier):
    return TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)

def test_execute_trade_from_social_media_bitcoin_high_confidence(decision_manager, mock_trader, monkeypatch):
    # Arrange
    monkeypatch.setenv("PROD_EXECUTION", "True")
    monkeypatch.setenv("TS_ORDER_AMOUNT_BITCOIN_BUY_HIGH_CONF", "0.02")
    monkeypatch.setenv("TS_LEVERAGE_BITCOIN_BUY_HIGH_CONF", "25")
    
    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="bitcoin",
        price_direction="up",
        price_confidence=0.99 # Above default high threshold
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-1")

    # Assert
    mock_trader.execute_order.assert_called_once()
    called_args, _ = mock_trader.execute_order.call_args
    assert called_args[1] == 0.02 # amount
    assert called_args[2] == 25   # leverage

def test_execute_trade_from_social_media_tariffs_med_confidence(decision_manager, mock_trader, monkeypatch):
    # Arrange
    monkeypatch.setenv("PROD_EXECUTION", "True")
    monkeypatch.setenv("TS_ORDER_AMOUNT_SHORT_MED_CONF", "-0.05")
    monkeypatch.setenv("TS_LEVERAGE_SHORT_MED_CONF", "8")
    monkeypatch.setenv("TS_CONFIDENCE_THRESHOLD_MED", "0.85")

    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="tariffs",
        price_direction="down",
        price_confidence=0.86 # Above medium threshold
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-2")

    # Assert
    mock_trader.execute_order.assert_called_once()
    called_args, _ = mock_trader.execute_order.call_args
    assert called_args[1] == -0.05 # amount
    assert called_args[2] == 8    # leverage

def test_no_trade_if_confidence_too_low(decision_manager, mock_trader, monkeypatch):
    # Arrange
    monkeypatch.setenv("PROD_EXECUTION", "True")
    
    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="market",
        price_direction="up",
        price_confidence=0.70 # Below default medium threshold of 0.9
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-3")

    # Assert
    mock_trader.execute_order.assert_not_called()

def test_no_trade_for_irrelevant_topic(decision_manager, mock_trader, monkeypatch):
    # Arrange
    monkeypatch.setenv("PROD_EXECUTION", "True")
    
    analysis_result = SocialMediaAnalysisOutput(
        topic_classification="others",
        price_direction="up",
        price_confidence=0.99
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-4")

    # Assert
    mock_trader.execute_order.assert_not_called()
