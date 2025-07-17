import pytest
from unittest.mock import MagicMock, AsyncMock

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.models import FEDDecisionImpact, FailedFEDAnalysis

# Mark all tests in this file to be run with asyncio support
pytestmark = pytest.mark.asyncio


async def test_fed_analyzer_handles_successful_analysis(mocker):
    """
    Tests the success case where the AI agent returns a valid result.
    The test is now async to properly await the analyze_content method.
    """
    # 1. Arrange
    # Create a mock result that the AI agent should return.
    mock_ai_output = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=0.95,
        reasoning="The decision was more dovish than expected.",
        actual_fed_decision_summary="Rates were held steady."
    )

    # Use AsyncMock for the agent's 'run' method, as it's an awaitable.
    mock_agent_instance = MagicMock()
    # The agent's run method returns a container object with an 'output' attribute.
    # We configure the mock to return a coroutine that resolves to this object.
    mock_agent_instance.run = AsyncMock(return_value=MagicMock(output=mock_ai_output))

    # Patch the _initialize_agent method on the class to return our mock instance.
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)

    # Patch the loading of expectations to avoid file system access during the unit test.
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._load_expectations')

    analyzer = FEDDecisionAnalyzer()

    # 2. Act
    # Await the async method call.
    result = await analyzer.analyze_content("Some FED announcement text.")

    # 3. Assert
    assert isinstance(result, FEDDecisionImpact)
    assert result.impact_on_bitcoin == "positive"
    assert result.confidence == 0.95
    assert result.fed_chair_event is None
    # Ensure the agent's run method was called exactly once with the correct content.
    mock_agent_instance.run.assert_awaited_once_with("Some FED announcement text.")


async def test_fed_analyzer_handles_failed_analysis(mocker):
    """
    Tests the failure case where the AI agent returns a failure object.
    """
    # 1. Arrange
    # Create a mock failure object.
    mock_ai_failure = FailedFEDAnalysis(error_message="Could not parse content.")

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=MagicMock(output=mock_ai_failure))

    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._load_expectations')

    analyzer = FEDDecisionAnalyzer()

    # 2. Act
    result = await analyzer.analyze_content("Gibberish text.")

    # 3. Assert
    assert isinstance(result, FailedFEDAnalysis)
    assert "agent failed" in result.error_message


async def test_fed_analyzer_detects_chair_event(mocker):
    """Ensures the analyzer returns the fed_chair_event field when present."""
    mock_ai_output = FEDDecisionImpact(
        impact_on_bitcoin="negative",
        confidence=0.9,
        reasoning="Leadership change creates uncertainty",
        actual_fed_decision_summary="Rates unchanged",
        fed_chair_event="Powell fired",
    )

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=MagicMock(output=mock_ai_output))

    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._load_expectations')

    analyzer = FEDDecisionAnalyzer()
    result = await analyzer.analyze_content("Powell was dismissed by the President.")

    assert isinstance(result, FEDDecisionImpact)
    assert result.fed_chair_event == "Powell fired"