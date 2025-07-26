
import pytest
import json
from app.models import SocialMediaAnalysisOutput

pytestmark = pytest.mark.e2e

@pytest.fixture
def tariffs_payload():
    with open("tests/testdata/ts_tariffs_hawkish.json") as f:
        data = json.load(f)
    if 'content_id' in data:
        data['content-id'] = data.pop('content_id')
    return data

def test_social_media_flow(test_app_client, tariffs_payload):
    client, mocks = test_app_client
    
    # Arrange
    mocks["social_analyzer"].analyze_content.return_value = SocialMediaAnalysisOutput(
        price_direction="down", price_confidence=0.96
    )

    # Act
    response = client.post("/notify/truth-social", json=tariffs_payload)

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mocks["social_analyzer"].analyze_content.assert_awaited_once()
    mocks["trade_manager"].execute_trade_from_analysis.assert_called_once()

def test_duplicate_social_media_flow(test_app_client, tariffs_payload):
    client, mocks = test_app_client

    # Act
    response1 = client.post("/notify/truth-social", json=tariffs_payload)
    response2 = client.post("/notify/truth-social", json=tariffs_payload)

    # Assert
    assert response1.status_code == 200
    assert response2.status_code == 409
    mocks["social_analyzer"].analyze_content.assert_called_once()
