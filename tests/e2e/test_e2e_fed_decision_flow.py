
import pytest
from unittest.mock import AsyncMock
from app.models import FEDDecisionImpact

pytestmark = pytest.mark.e2e

def test_e2e_fed_flow(test_app_client):
    client, mocks = test_app_client
    
    # Arrange
    mocks["fed_analyzer"].analyze_content.return_value = FEDDecisionImpact(
        impact_on_bitcoin="positive", confidence=0.99, reasoning="", actual_fed_decision_summary=""
    )
    payload = {
        "type": "web-monitor",
        "url": "http://test.com/fed-news",
        "content": "dovish content here",
        "ip": "127.0.0.1"
    }

    # Act
    response = client.post("/notify/web-monitor", json=payload)

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mocks["fed_analyzer"].analyze_content.assert_awaited_once()
    mocks["trade_manager"].execute_trade_from_analysis.assert_called_once()
