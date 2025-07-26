
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app 
from app.models import SocialMediaAnalysisOutput

client = TestClient(app)

@pytest.fixture
def tariffs_payload():
    with open("tests/testdata/ts_tariffs_hawkish.json") as f:
        return json.load(f)

@patch("app.main.TradeDecisionManager")
@patch("app.main.SocialMediaPostAnalyzer")
def test_social_media_notification_e2e_flow(MockedSocialMediaAnalyzer, MockedTradeDecisionManager, tariffs_payload):
    # Arrange
    # Mock the analyzer to return a predictable result
    mock_analyzer_instance = MockedSocialMediaAnalyzer.return_value
    mock_analyzer_instance.analyze_content.return_value = SocialMediaAnalysisOutput(
        topic_classification="tariffs",
        price_direction="down",
        price_confidence=0.96
    )

    # Mock the trade decision manager
    mock_manager_instance = MockedTradeDecisionManager.return_value

    # Act
    response = client.post("/notify", json=tariffs_payload)

    # Assert
    # 1. Check HTTP Response
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Notification processed and trade logic triggered."}

    # 2. Check that the correct analyzer was called
    mock_analyzer_instance.analyze_content.assert_called_once_with(
        tariffs_payload["content"],
        tariffs_payload["content_id"]
    )

    # 3. Check that the trade manager was called with the result from the analyzer
    mock_manager_instance.execute_trade_from_analysis.assert_called_once()
    call_args, _ = mock_manager_instance.execute_trade_from_analysis.call_args
    assert isinstance(call_args[0], SocialMediaAnalysisOutput)
    assert call_args[0].price_direction == "down"
    assert call_args[1] == tariffs_payload["content_id"]

@patch("app.main.SocialMediaPostAnalyzer")
def test_duplicate_social_media_post_is_rejected(MockedSocialMediaAnalyzer, tariffs_payload):
    # Arrange
    mock_analyzer_instance = MockedSocialMediaAnalyzer.return_value
    mock_analyzer_instance.analyze_content.return_value = SocialMediaAnalysisOutput(
        topic_classification="tariffs", price_direction="down", price_confidence=0.99
    )
    
    # Act
    # Send the first request
    response1 = client.post("/notify", json=tariffs_payload)
    
    # Send the exact same request again
    response2 = client.post("/notify", json=tariffs_payload)

    # Assert
    assert response1.status_code == 200
    assert response2.status_code == 409 # Conflict
    assert "already processed" in response2.json()["detail"]
    
    # Ensure the analyzer was only called once
    mock_analyzer_instance.analyze_content.assert_called_once()
