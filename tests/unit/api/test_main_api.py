# tests/unit/api/test_main_api.py

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import FEDDecisionImpact, FailedFEDAnalysis


# No need to create the client here globally anymore.
# We will create it inside each test function to manage the lifespan context.

def test_web_monitor_notification_success_flow(mocker):
    """
    Tests the complete success flow of the /notify/web-monitor endpoint.
    Mocks internal services to test the API layer in isolation.
    """
    # 1. Arrange
    # Define what our mock services should return
    successful_analysis = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=0.99,
        reasoning="Mocked positive impact",
        actual_fed_decision_summary="Mocked summary"
    )

    # Mock the classes that are instantiated within the lifespan manager
    # We patch them before the lifespan manager is entered.
    mocker.patch('app.main.FEDDecisionAnalyzer',
                 return_value=MagicMock(analyze_content=MagicMock(return_value=successful_analysis)))

    # Mock the TradeDecisionManager to check if it's called
    mock_trade_manager_instance = MagicMock()
    mocker.patch('app.main.TradeDecisionManager', return_value=mock_trade_manager_instance)

    # We also mock the other initializers to prevent side effects (like real Bitfinex calls)
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {
        "uuid": "test-uuid-123",
        "type": "web-monitor",
        "url": "http://test.com",
        "content-id": "fomc-minutes",
        "content": "The FED decided to be very positive today.",
        "ip": "127.0.0.1"
    }

    # 2. Act
    # Use the TestClient as a context manager to correctly handle the lifespan events.
    with TestClient(app) as client:
        response = client.post("/notify/web-monitor", json=payload)

    # 3. Assert
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Notification processed and trade logic triggered."}

    # The TradeDecisionManager instance was created by the mocked constructor.
    # Now we can check if its method was called.
    mock_trade_manager_instance.execute_trade_from_analysis.assert_called_once()

    # Verify the arguments passed to the method
    call_args, call_kwargs = mock_trade_manager_instance.execute_trade_from_analysis.call_args
    assert call_kwargs['analysis_result'] == successful_analysis
    assert call_kwargs['content_id_for_log'] == "fomc-minutes"


def test_web_monitor_notification_analyzer_fails(mocker):
    """Tests the case where the AI analyzer fails."""
    # 1. Arrange
    failed_analysis = FailedFEDAnalysis(error_message="AI failed spectacularly")

    # Patch the FEDDecisionAnalyzer to return the failure object
    mocker.patch('app.main.FEDDecisionAnalyzer',
                 return_value=MagicMock(analyze_content=MagicMock(return_value=failed_analysis)))

    # We don't need to mock the trade manager here as it shouldn't be reached
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {"type": "web-monitor", "content": "bad content", "ip": "127.0.0.1"}

    # 2. Act
    with TestClient(app) as client:
        response = client.post("/notify/web-monitor", json=payload)

    # 3. Assert
    assert response.status_code == 500
    assert "FED analysis failed" in response.json()['detail']