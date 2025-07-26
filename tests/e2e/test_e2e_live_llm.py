

import pytest
import asyncio
import logging
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.config import AppConfig
from app.trading.bitfinex_trader import BitfinexTrader

# Mark all tests in this file with 'e2e' and 'live_llm'
pytestmark = [pytest.mark.e2e, pytest.mark.live_llm]

@pytest.fixture(scope="function")
def live_llm_test_client(mocker):
    """
    Provides a TestClient where the AI agent is REAL, but the trader is MOCKED.
    This mocks the BitfinexTrader in a way that passes isinstance checks.
    """
    # Create a mock that looks like an instance of BitfinexTrader
    mock_bfx_trader = MagicMock(spec=BitfinexTrader)
    mock_bfx_trader.bfx_client = MagicMock() # Ensure the client attribute exists
    
    # Patch the class to return our specialized mock instance
    mocker.patch("app.main.BitfinexTrader", return_value=mock_bfx_trader)

    from app.main import app
    with TestClient(app) as client:
        yield client

@pytest.mark.asyncio
async def test_e2e_live_llm_flow_with_dovish_fed_statement(live_llm_test_client, caplog, mocker):
    """
    Tests the complete E2E flow with a real LLM call and PROD_EXECUTION=False.
    """
    # 1. Arrange
    assert not AppConfig.PROD_EXECUTION, "This test must run with PROD_EXECUTION=False"
    caplog.set_level(logging.INFO)

    dovish_content = (
        "In a surprising move, the Federal Open Market Committee (FOMC) announced today "
        "they will not only hold interest rates steady but also signaled a potential "
        "rate cut sooner than anticipated. Chairman Powell mentioned concerns about "
        "slowing economic growth, suggesting a more accommodative monetary policy "
        "is necessary to support the market. This dovish pivot was unexpected."
    )
    payload = {
        "uuid": "e2e-live-dovish-sim-123",
        "type": "web-monitor",
        "url": "http://e2e-test.com/dovish-statement-sim-live",
        "content_id": "fomc-dovish-e2e-sim-live",
        "content": dovish_content,
        "ip": "127.0.0.1"
    }
    
    # Temporarily lower the confidence threshold for this test to make it robust
    mocker.patch.object(AppConfig, 'CONFIDENCE_THRESHOLD_FED_MED', 0.75)
    mocker.patch.object(AppConfig, 'CONFIDENCE_THRESHOLD_FED_HIGH', 0.95)

    # 2. Act
    response = live_llm_test_client.post("/notify/web-monitor", json=payload)
    await asyncio.sleep(0.1) # Allow background tasks to run

    # 3. Assert
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    simulation_log_found = False
    for record in caplog.records:
        if "Simulating order execution" in record.message:
            simulation_log_found = True
            break

    assert simulation_log_found, "The log message for simulating a BUY/LONG trade was not found."
    print("\n--- E2E LIVE LLM VERIFICATION SUCCESS ---")

