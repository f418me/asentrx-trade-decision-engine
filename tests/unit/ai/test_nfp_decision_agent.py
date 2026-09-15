from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.agents.nfp_decision_agent import NFPDecisionAnalyzer
from app.models import FailedNFPAnalysis, NFPReportImpact

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_analyze_content_returns_nfp_impact(mocker):
    mock_ai_output = NFPReportImpact(
        impact_on_bitcoin="positive",
        confidence=0.91,
        reasoning="Payrolls and wages were softer than expected.",
        actual_report_summary="Soft report.",
        actual_nonfarm_payrolls_k=10,
        actual_unemployment_rate=4.3,
        actual_average_hourly_earnings_mom=0.1,
        actual_average_hourly_earnings_yoy=3.1,
    )
    mock_result = MagicMock()
    mock_result.output = mock_ai_output
    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=mock_result)

    mocker.patch('app.ai.agents.nfp_decision_agent.NFPDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)
    mocker.patch('app.ai.agents.nfp_decision_agent.NFPDecisionAnalyzer._load_expectations')

    analyzer = NFPDecisionAnalyzer()
    result = await analyzer.analyze_content("Employment Situation release text.")

    assert isinstance(result, NFPReportImpact)
    assert result.impact_on_bitcoin == "positive"
    mock_agent_instance.run.assert_awaited_once_with("Employment Situation release text.")


@pytest.mark.asyncio
async def test_analyze_content_returns_failed_analysis(mocker):
    mock_ai_failure = FailedNFPAnalysis(error_message="Could not parse content.")
    mock_result = MagicMock()
    mock_result.output = mock_ai_failure
    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=mock_result)

    mocker.patch('app.ai.agents.nfp_decision_agent.NFPDecisionAnalyzer._initialize_agent', return_value=mock_agent_instance)
    mocker.patch('app.ai.agents.nfp_decision_agent.NFPDecisionAnalyzer._load_expectations')

    analyzer = NFPDecisionAnalyzer()
    result = await analyzer.analyze_content("Employment Situation release text.")

    assert isinstance(result, FailedNFPAnalysis)
    assert "Could not parse content" in result.error_message
