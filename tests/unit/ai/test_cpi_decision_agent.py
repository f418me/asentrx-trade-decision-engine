from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.agents.cpi_decision_agent import CPIDecisionAnalyzer
from app.models import CPIReportImpact, FailedCPIAnalysis

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_analyze_content_returns_cpi_impact(mocker):
    mock_ai_output = CPIReportImpact(
        impact_on_bitcoin="positive",
        confidence=0.91,
        reasoning="Core CPI was cooler than expected.",
        actual_report_summary="Cooler CPI report.",
        actual_headline_cpi_mom=0.1,
        actual_headline_cpi_yoy=3.3,
        actual_core_cpi_mom=0.1,
        actual_core_cpi_yoy=2.3,
    )
    mock_result = MagicMock()
    mock_result.output = mock_ai_output
    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=mock_result)

    mocker.patch("app.ai.agents.cpi_decision_agent.CPIDecisionAnalyzer._initialize_agent", return_value=mock_agent_instance)
    mocker.patch("app.ai.agents.cpi_decision_agent.CPIDecisionAnalyzer._load_expectations")

    analyzer = CPIDecisionAnalyzer()
    result = await analyzer.analyze_content("Consumer Price Index release text.")

    assert isinstance(result, CPIReportImpact)
    assert result.impact_on_bitcoin == "positive"
    mock_agent_instance.run.assert_awaited_once_with("Consumer Price Index release text.")


@pytest.mark.asyncio
async def test_analyze_content_returns_failed_analysis(mocker):
    mock_ai_failure = FailedCPIAnalysis(error_message="Could not parse content.")
    mock_result = MagicMock()
    mock_result.output = mock_ai_failure
    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=mock_result)

    mocker.patch("app.ai.agents.cpi_decision_agent.CPIDecisionAnalyzer._initialize_agent", return_value=mock_agent_instance)
    mocker.patch("app.ai.agents.cpi_decision_agent.CPIDecisionAnalyzer._load_expectations")

    analyzer = CPIDecisionAnalyzer()
    result = await analyzer.analyze_content("Consumer Price Index release text.")

    assert isinstance(result, FailedCPIAnalysis)
    assert "Could not parse content" in result.error_message
