
import pytest
from unittest.mock import AsyncMock, patch
from app.ai.agents.social_media_agent import SocialMediaPostAnalyzer, TopicClassification, PriceDirectionPrediction, SocialMediaAnalysisOutput

@pytest.fixture
def analyzer():
    return SocialMediaPostAnalyzer()

@pytest.mark.asyncio
@patch('app.ai.agents.social_media_agent.topic_classification_agent.run', new_callable=AsyncMock)
@patch('app.ai.agents.social_media_agent.bitcoin_price_direction_agent.run', new_callable=AsyncMock)
async def test_analyze_content_bitcoin_up(mock_bitcoin_agent, mock_topic_agent, analyzer):
    # Arrange
    mock_topic_agent.return_value = TopicClassification(
        classification="bitcoin",
        confidence=0.98,
        reasoning="The post explicitly mentions Bitcoin."
    )
    mock_bitcoin_agent.return_value = PriceDirectionPrediction(
        direction="up",
        confidence=0.92,
        reasoning="The sentiment is overwhelmingly positive."
    )
    content = "Bitcoin to the moon! #BTC"

    # Act
    result = await analyzer.analyze_content(content, "test-id-1")

    # Assert
    assert isinstance(result, SocialMediaAnalysisOutput)
    assert result.topic_classification == "bitcoin"
    assert result.price_direction == "up"
    assert result.price_confidence == 0.92
    mock_topic_agent.assert_called_once_with(content)
    mock_bitcoin_agent.assert_called_once_with(content)

@pytest.mark.asyncio
@patch('app.ai.agents.social_media_agent.topic_classification_agent.run', new_callable=AsyncMock)
@patch('app.ai.agents.social_media_agent.tariffs_impact_direction_agent.run', new_callable=AsyncMock)
async def test_analyze_content_tariffs_down(mock_tariffs_agent, mock_topic_agent, analyzer):
    # Arrange
    mock_topic_agent.return_value = TopicClassification(
        classification="tariffs",
        confidence=0.99,
        reasoning="The post is about new tariffs."
    )
    mock_tariffs_agent.return_value = PriceDirectionPrediction(
        direction="down",
        confidence=0.88,
        reasoning="Increased tariffs are generally negative for markets."
    )
    content = "New 25% tariffs on all goods from EU."

    # Act
    result = await analyzer.analyze_content(content, "test-id-2")

    # Assert
    assert result.topic_classification == "tariffs"
    assert result.price_direction == "down"
    assert result.price_confidence == 0.88
    mock_topic_agent.assert_called_once_with(content)
    mock_tariffs_agent.assert_called_once_with(content)

@pytest.mark.asyncio
@patch('app.ai.agents.social_media_agent.topic_classification_agent.run', new_callable=AsyncMock)
@patch('app.ai.agents.social_media_agent.market_price_direction_agent.run', new_callable=AsyncMock)
async def test_analyze_content_others_no_direction(mock_market_agent, mock_topic_agent, analyzer):
    # Arrange
    mock_topic_agent.return_value = TopicClassification(
        classification="others",
        confidence=0.95,
        reasoning="This is a general political statement."
    )
    content = "Happy 4th of July!"

    # Act
    result = await analyzer.analyze_content(content, "test-id-3")

    # Assert
    assert result.topic_classification == "others"
    assert result.price_direction is None
    assert result.price_confidence is None
    mock_topic_agent.assert_called_once_with(content)
    mock_market_agent.assert_not_called() # Ensure no direction agent was called
