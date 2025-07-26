

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import logging

from app.main import app
from app.config import AppConfig
from app.models import FEDDecisionImpact

# Mark all tests in this file with both 'e2e' and 'live_llm'
pytestmark = [pytest.mark.e2e, pytest.mark.live_llm]

@pytest.fixture(scope="function")
def live_llm_test_client(mocker):
    """
    Provides a TestClient where the AI agents are REAL, but the trader is MOCKED.
    This allows testing the actual LLM integration without executing trades.
    """
    # Mock only the TradeDecisionManager to prevent any trading actions
    mock_trade_manager = MagicMock()
    mocker.patch("app.main.TradeDecisionManager", return_value=mock_trade_manager)

    # The other services (BitfinexTrader, AI Agents) will be initialized as normal
    from app.main import app
    with TestClient(app) as client:
        yield client, mock_trade_manager

def test_live_llm_fed_dovish_statement(live_llm_test_client, caplog):
    """
    Tests the E2E flow with a REAL LLM call for a dovish statement.
    PROD_EXECUTION must be False in .env.test to ensure no real trades.
    """
    # 1. Arrange
    client, mock_trade_manager = live_llm_test_client
    caplog.set_level(logging.INFO)

    # Ensure we are in simulation mode
    assert not AppConfig.PROD_EXECUTION, "This test must run with PROD_EXECUTION=False"

    dovish_content = (
        "In a surprising move, the Federal Open Market Committee (FOMC) announced today "
        "they will not only hold interest rates steady but also signaled a potential "
        "rate cut sooner than anticipated. Chairman Powell mentioned concerns about "
        "slowing economic growth, suggesting a more accommodative monetary policy "
        "is necessary to support the market. This dovish pivot was unexpected."
    )
    payload = {
        "uuid": "e2e-live-llm-dovish-001",
        "type": "web-monitor",
        "url": "http://e2e-test.com/live-llm-dovish",
        "content_id": "fomc-live-llm-dovish",
        "content": dovish_content,
        "ip": "127.0.0.1"
    }

    # 2. Act
    response = client.post("/notify/web-monitor", json=payload)

    # 3. Assert
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Check that the trade manager was called, indicating the AI analysis was successful
    mock_trade_manager.execute_trade_from_analysis.assert_called_once()
    
    # Verify the analysis result passed to the manager looks correct
    call_args, _ = mock_trade_manager.execute_trade_from_analysis.call_args
    analysis_result = call_args[0]
    
    assert isinstance(analysis_result, FEDDecisionImpact)
    assert analysis_result.impact_on_bitcoin == "positive"
    assert analysis_result.confidence > 0.7 # Check for a reasonable confidence score
    
    print(f"\nLive LLM test successful. AI analysis result: {analysis_result.impact_on_bitcoin} with confidence {analysis_result.confidence:.2f}")

