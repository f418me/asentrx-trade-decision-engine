import pytest
import asyncio
import logging
from unittest.mock import MagicMock, patch

from app.config import AppConfig

# Mark all tests in this file as 'e2e'
pytestmark = pytest.mark.e2e

# We need to manually set PROD_EXECUTION to False from our test environment for this scenario
# This assumes your .env.test file has PROD_EXECUTION=False
assert not AppConfig.PROD_EXECUTION, "E2E tests for simulation mode require PROD_EXECUTION=False in .env.test"


@pytest.mark.asyncio
async def test_e2e_flow_with_dovish_fed_statement(test_app_client, caplog, mocker):
    """
    Tests the complete E2E flow with PROD_EXECUTION=False.
    It makes a real request to the LLM and simulates the trade execution.
    Scenario: A dovish FED statement should result in a positive impact
    on Bitcoin and trigger a simulated BUY trade.
    """
    # 1. Arrange
    # A realistic, fictitious text representing a dovish surprise.
    # The LLM should identify a positive impact.
    dovish_content = (
        "In a surprising move, the Federal Open Market Committee (FOMC) announced today "
        "they will not only hold interest rates steady but also signaled a potential "
        "rate cut sooner than anticipated. Chairman Powell mentioned concerns about "
        "slowing economic growth, suggesting a more accommodative monetary policy "
        "is necessary to support the market. This dovish pivot was unexpected."
    )

    payload = {
        "uuid": "e2e-dovish-sim-123",
        "type": "web-monitor",
        "url": "http://e2e-test.com/dovish-statement-sim",
        "content-id": "fomc-dovish-e2e-sim",
        "content": dovish_content,
        "ip": "127.0.0.1"
    }

    # Set the log level to INFO to capture relevant messages if needed for debugging.
    caplog.set_level(logging.INFO)

    # Patch the confidence thresholds for robust testing.
    mocker.patch.object(AppConfig, 'CONFIDENCE_THRESHOLD_FED_MED', 0.85)
    mocker.patch.object(AppConfig, 'CONFIDENCE_THRESHOLD_FED_HIGH', 0.95)

    # KEY FIX: Mock the TradeDecisionManager to avoid dependency on real API keys.
    # This mock will be injected into app.state during initialization.
    mock_trade_manager = MagicMock()

    # We patch TradeDecisionManager in the 'app.main' namespace where it's used.
    # The `with` block ensures the patch is only active for this test.
    with patch('app.main.TradeDecisionManager', return_value=mock_trade_manager):
        # 2. Act
        print("\n--- Sending E2E request for dovish simulation scenario ---")
        # The test_app_client fixture initializes the app within this patched context.
        response = test_app_client.post("/notify/web-monitor", json=payload)
        print(f"--- Received response: {response.status_code} {response.text} ---")

    # The `await` is not strictly necessary here since the `post` call is synchronous,
    # but it can help ensure any background tasks have a moment to complete.
    await asyncio.sleep(0.1)

    # 3. Assert
    assert response.status_code == 200, f"Expected status 200, but got {response.status_code}. Response: {response.text}"
    assert response.json()["status"] == "success"

    # Assert that our mock manager's method was called, which is more robust than checking logs.
    mock_trade_manager.execute_trade_from_analysis.assert_called_once()

    # Optionally, inspect the arguments passed to the mock to verify the AI analysis was correct.
    # call_args is a tuple: (args, kwargs)
    call_args, call_kwargs = mock_trade_manager.execute_trade_from_analysis.call_args
    analysis_result = call_kwargs['analysis_result']

    assert analysis_result.impact_on_bitcoin == 'positive'
    assert analysis_result.confidence >= AppConfig.CONFIDENCE_THRESHOLD_FED_MED

    print("\n--- E2E VERIFICATION SUCCESS ---")
    print("Mocked TradeDecisionManager was correctly called with a 'positive' impact analysis.")


@pytest.mark.asyncio
@pytest.mark.skip(reason="Skipping hawkish scenario for now. Can be enabled after fixing with mock.")
async def test_e2e_flow_with_hawkish_fed_statement(test_app_client, caplog, mocker):
    """
    Tests the E2E flow for a hawkish statement with PROD_EXECUTION=False.
    Expected outcome: negative impact -> call to trade manager with 'negative' analysis.
    """
    # 1. Arrange
    hawkish_content = (
        "The Federal Reserve today announced a surprise 0.25% interest rate hike, "
        "citing persistent inflationary pressures. Chairman Powell's remarks were "
        "decidedly hawkish, emphasizing the committee's resolve to bring inflation "
        "back to the 2% target, even at the risk of a short-term economic slowdown."
    )
    payload = {
        "uuid": "e2e-hawkish-sim-456",
        "type": "web-monitor",
        "content": hawkish_content,
        "ip": "127.0.0.1"
    }

    caplog.set_level(logging.INFO)
    mocker.patch.object(AppConfig, 'CONFIDENCE_THRESHOLD_FED_MED', 0.85)
    mocker.patch.object(AppConfig, 'CONFIDENCE_THRESHOLD_FED_HIGH', 0.95)

    # Mock the TradeDecisionManager for this test as well
    mock_trade_manager = MagicMock()
    with patch('app.main.TradeDecisionManager', return_value=mock_trade_manager):
        # 2. Act
        print("\n--- Sending E2E request for hawkish simulation scenario ---")
        response = test_app_client.post("/notify/web-monitor", json=payload)
        print(f"--- Received response: {response.status_code} {response.text} ---")

    await asyncio.sleep(0.1)

    # 3. Assert
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify the mock was called correctly
    mock_trade_manager.execute_trade_from_analysis.assert_called_once()

    call_args, call_kwargs = mock_trade_manager.execute_trade_from_analysis.call_args
    analysis_result = call_kwargs['analysis_result']

    assert analysis_result.impact_on_bitcoin == 'negative'

    print("\n--- E2E VERIFICATION SUCCESS ---")
    print("Mocked TradeDecisionManager was correctly called with a 'negative' impact analysis.")