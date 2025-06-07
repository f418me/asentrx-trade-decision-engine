from unittest.mock import MagicMock

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.models import FEDDecisionImpact, FailedFEDAnalysis


def test_fed_analyzer_handles_successful_analysis(mocker):
    """
    Tests the success case where the AI agent returns a valid result.
    'mocker' is a fixture provided by pytest-mock.
    """
    # 1. Arrange
    # Create a mock result that the AI agent should return.
    mock_ai_output = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=0.95,
        reasoning="The decision was more dovish than expected.",
        actual_fed_decision_summary="Rates were held steady."
    )

    # Create a mock for the pydantic-ai Agent instance and its run_sync method.
    mock_agent_instance = MagicMock()
    # The agent's run_sync method returns a container object with an 'output' attribute.
    mock_agent_instance.run_sync.return_value = MagicMock(output=mock_ai_output)

    # Patch the _initialize_agent method on the class to return our mock instance.
    # The path string points to the location of the class being tested.
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)

    # Patch the loading of expectations to avoid file system access during the unit test.
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._load_expectations')

    analyzer = FEDDecisionAnalyzer()

    # 2. Act
    result = analyzer.analyze_content("Some FED announcement text.")

    # 3. Assert
    assert isinstance(result, FEDDecisionImpact)
    assert result.impact_on_bitcoin == "positive"
    assert result.confidence == 0.95
    # Ensure the agent's run_sync method was called exactly once with the correct content.
    mock_agent_instance.run_sync.assert_called_once_with("Some FED announcement text.")


def test_fed_analyzer_handles_failed_analysis(mocker):
    """
    Tests the failure case where the AI agent returns a failure object.
    """
    # 1. Arrange
    # Create a mock failure object.
    mock_ai_failure = FailedFEDAnalysis(error_message="Could not parse content.")

    mock_agent_instance = MagicMock()
    mock_agent_instance.run_sync.return_value = MagicMock(output=mock_ai_failure)

    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)
    mocker.patch('app.ai.agents.fed_decision_agent.FEDDecisionAnalyzer._load_expectations')

    analyzer = FEDDecisionAnalyzer()

    # 2. Act
    result = analyzer.analyze_content("Gibberish text.")

    # 3. Assert
    assert isinstance(result, FailedFEDAnalysis)
    assert "agent failed" in result.error_message