import pytest
from unittest.mock import MagicMock
from app.trading.trade_decision_manager import TradeDecisionManager
from app.models import SocialMediaMarketSignal
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

    analysis_result = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="crypto_policy_positive",
        asset="btc",
        direction="up",
        confidence=0.99, # Above default high threshold
        novelty_score=0.90,
        time_sensitivity="immediate",
        risk_level="medium",
        reasoning="Concrete new crypto policy.",
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

    analysis_result = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="tariff_escalation",
        asset="broad_market",
        direction="down",
        confidence=0.86, # Above medium threshold
        novelty_score=0.80,
        time_sensitivity="same_day",
        risk_level="high",
        reasoning="New tariff escalation.",
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
    
    analysis_result = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="fiscal_policy",
        asset="broad_market",
        direction="up",
        confidence=0.70, # Below default medium threshold of 0.9
        novelty_score=0.90,
        time_sensitivity="immediate",
        risk_level="medium",
        reasoning="Direction is too uncertain.",
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-3")

    # Assert
    mock_trader.execute_order.assert_not_called()

def test_no_trade_for_non_tradeable_signal(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)
    
    analysis_result = SocialMediaMarketSignal(
        is_tradeable=False,
        event_type="non_tradeable",
        asset="none",
        direction="neutral",
        confidence=0.99,
        novelty_score=0.10,
        time_sensitivity="none",
        risk_level="low",
        reasoning="Generic slogan.",
        trade_veto_reason="No concrete catalyst.",
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-4")

    # Assert
    mock_trader.execute_order.assert_not_called()

def test_no_trade_if_novelty_too_low(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)

    analysis_result = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="tariff_escalation",
        asset="broad_market",
        direction="down",
        confidence=0.99,
        novelty_score=0.40,
        time_sensitivity="immediate",
        risk_level="medium",
        reasoning="A repeated tariff statement with little new information.",
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-5")

    # Assert
    mock_trader.execute_order.assert_not_called()

def test_no_trade_if_timing_is_slow(mock_trader, mock_sms_notifier, mocker):
    # Arrange
    mocker.patch.object(AppConfig, 'PROD_EXECUTION', True)
    decision_manager = TradeDecisionManager(trader=mock_trader, sms_notifier=mock_sms_notifier)

    analysis_result = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="fiscal_policy",
        asset="broad_market",
        direction="up",
        confidence=0.99,
        novelty_score=0.90,
        time_sensitivity="slow",
        risk_level="medium",
        reasoning="The catalyst is not an immediate trading signal.",
    )

    # Act
    decision_manager.execute_trade_from_analysis(analysis_result, "ts-test-6")

    # Assert
    mock_trader.execute_order.assert_not_called()
