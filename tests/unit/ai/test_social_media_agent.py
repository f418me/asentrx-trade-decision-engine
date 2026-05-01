
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.ai.agents.social_media_agent import SocialMediaPostAnalyzer
from app.models import IrrelevantSocialMediaContent, SocialMediaMarketSignal

@pytest.fixture
def analyzer(mocker):
    mock_agent = MagicMock()
    mocker.patch(
        "app.ai.agents.social_media_agent.SocialMediaPostAnalyzer._initialize_agent",
        return_value=mock_agent,
    )
    return SocialMediaPostAnalyzer()

@pytest.mark.asyncio
async def test_analyze_content_crypto_policy_up(analyzer):
    # Arrange
    signal = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="crypto_policy_positive",
        asset="btc",
        direction="up",
        confidence=0.98,
        novelty_score=0.91,
        time_sensitivity="immediate",
        risk_level="medium",
        reasoning="The post announces a concrete new pro-crypto policy.",
    )
    analyzer.agent.run = AsyncMock(return_value=MagicMock(output=signal))
    content = "Bitcoin to the moon! #BTC"

    # Act
    result = await analyzer.analyze_content(content, "test-id-1")

    # Assert
    assert isinstance(result, SocialMediaMarketSignal)
    assert result.event_type == "crypto_policy_positive"
    assert result.direction == "up"
    assert result.confidence == 0.98
    analyzer.agent.run.assert_awaited_once_with(content)

@pytest.mark.asyncio
async def test_analyze_content_tariffs_down(analyzer):
    # Arrange
    signal = SocialMediaMarketSignal(
        is_tradeable=True,
        event_type="tariff_escalation",
        asset="broad_market",
        direction="down",
        confidence=0.99,
        novelty_score=0.86,
        time_sensitivity="same_day",
        risk_level="high",
        reasoning="A new tariff escalation is usually risk-off for Bitcoin.",
    )
    analyzer.agent.run = AsyncMock(return_value=MagicMock(output=signal))
    content = "New 25% tariffs on all goods from EU."

    # Act
    result = await analyzer.analyze_content(content, "test-id-2")

    # Assert
    assert result.event_type == "tariff_escalation"
    assert result.direction == "down"
    assert result.novelty_score == 0.86
    analyzer.agent.run.assert_awaited_once_with(content)

@pytest.mark.asyncio
async def test_analyze_content_others_returns_irrelevant(analyzer):
    # Arrange
    analyzer.agent.run = AsyncMock(
        return_value=MagicMock(output=IrrelevantSocialMediaContent(reason="General political statement."))
    )
    content = "Happy 4th of July!"

    # Act
    result = await analyzer.analyze_content(content, "test-id-3")

    # Assert
    assert isinstance(result, IrrelevantSocialMediaContent)
    assert "political" in result.reason
    analyzer.agent.run.assert_awaited_once_with(content)
