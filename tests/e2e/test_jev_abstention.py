from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.ai.jev_schemas import FEDJudgments

pytestmark = pytest.mark.e2e


def test_real_analyzer_abstention_never_reaches_trade_manager(test_app_client, mocker):
    client, mocks = test_app_client
    answers = FEDJudgments(
        is_fresh_release=True,
        actual_change_bp=0,
        actual_narrative="dovish",
        guidance_vs_baseline="more_dovish",
    )
    agent = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(
                output=answers,
                response=SimpleNamespace(provider_details=None, model_name="jev-test"),
            )
        )
    )
    mocker.patch.object(FEDDecisionAnalyzer, "_initialize_agent", return_value=agent)
    client.app.state.fed_decision_analyzer = FEDDecisionAnalyzer()
    response = client.post(
        "/notify/web-monitor",
        json={
            "url": "https://www.federalreserve.gov/release",
            "content": "Fresh FOMC announcement",
            "ip": "127.0.0.1",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success_no_action"
    mocks["trade_manager"].execute_trade_from_analysis.assert_not_called()
