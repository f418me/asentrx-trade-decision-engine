import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import FEDDecisionImpact, FailedFEDAnalysis, IrrelevantFEDContent

# pytest-Markierung, um sicherzustellen, dass alle Tests als Unit-Tests behandelt werden
pytestmark = pytest.mark.unit


def test_web_monitor_notification_rejects_already_processed_url(mocker):
    """
    Tests that a request is rejected with 409 Conflict if its URL is
    already in the 'processed_urls' set for the current session.
    """
    # 1. Arrange
    # Mocken der Abhängigkeiten, die im Lifespan-Manager initialisiert werden.
    mocker.patch('app.main.FEDDecisionAnalyzer')
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    processed_url = "http://test.com/i-am-already-processed"
    payload = {
        "uuid": "test-uuid-processed",
        "type": "web-monitor",
        "url": processed_url,
        "content": "some content",
        "ip": "127.0.0.1"
    }

    with TestClient(app) as client:
        # 2. Act: Simuliere den Zustand und sende die Anfrage
        # Füge die URL manuell zum Set hinzu, um eine bereits verarbeitete URL zu simulieren.
        client.app.state.processed_urls.add(processed_url)

        response = client.post("/notify/web-monitor", json=payload)

        # 3. Assert: Überprüfe die Ablehnung
        assert response.status_code == 409
        assert "has been processed in this session" in response.json()['detail']

        # Überprüfe, dass die URL immer noch im Set ist
        assert processed_url in client.app.state.processed_urls


def test_web_monitor_notification_success_flow_adds_url_to_set(mocker):
    """
    Tests the complete success flow and verifies that the URL is added
    to the processed set for the session.
    """
    # 1. Arrange
    successful_analysis = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=0.99,
        reasoning="Mocked positive impact",
        actual_fed_decision_summary="Mocked summary"
    )
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.analyze_content = AsyncMock(return_value=successful_analysis)
    mocker.patch('app.main.FEDDecisionAnalyzer', return_value=mock_analyzer_instance)
    mock_trade_manager_instance = MagicMock()
    mocker.patch('app.main.TradeDecisionManager', return_value=mock_trade_manager_instance)
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    unique_url = "http://test.com/unique-url-1"
    payload = {
        "uuid": "test-uuid-123",
        "type": "web-monitor",
        "url": unique_url,
        "content-id": "fomc-minutes",
        "content": "The FED decided to be very positive today.",
        "ip": "127.0.0.1"
    }

    # 2. Act
    with TestClient(app) as client:
        # Stelle sicher, dass das Set zu Beginn leer ist
        client.app.state.processed_urls.clear()

        response = client.post("/notify/web-monitor", json=payload)

    # 3. Assert
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Notification processed and trade logic triggered."}

    # Überprüfe, ob die Kernkomponenten aufgerufen wurden
    mock_analyzer_instance.analyze_content.assert_awaited_once()
    mock_trade_manager_instance.execute_trade_from_analysis.assert_called_once()

    # WICHTIG: Überprüfe, ob die URL dem Set hinzugefügt wurde
    assert unique_url in client.app.state.processed_urls


def test_web_monitor_notification_analyzer_fails_returns_200(mocker):
    """
    Tests that if the AI analyzer fails, the API returns a 200 OK status
    (or similar success-like code) and the URL is still marked as processed.
    """
    # 1. Arrange
    failed_analysis = FailedFEDAnalysis(error_message="AI failed spectacularly")
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.analyze_content = AsyncMock(return_value=failed_analysis)
    mocker.patch('app.main.FEDDecisionAnalyzer', return_value=mock_analyzer_instance)
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    fail_url = "http://test.com/unique-url-fail"
    payload = {"uuid": "test-uuid-fail", "type": "web-monitor", "url": fail_url, "content": "bad content",
               "ip": "127.0.0.1"}

    # 2. Act
    with TestClient(app) as client:
        client.app.state.processed_urls.clear()
        response = client.post("/notify/web-monitor", json=payload)

    # 3. Assert - Die Logik wurde geändert!
    assert response.status_code == 200
    assert response.json()["status"] == "success_analysis_failed"
    assert "analysis failed" in response.json()["message"]

    # WICHTIG: Überprüfe, ob die URL trotzdem als verarbeitet markiert wurde
    assert fail_url in client.app.state.processed_urls