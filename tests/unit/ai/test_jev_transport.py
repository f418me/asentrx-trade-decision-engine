"""Exercise real Pydantic AI and SDK serialization with an offline HTTP transport."""

import json

import httpx2
import pytest
from typesafe_sdk import AsyncTypeSafeClient

from app.ai.agents.fed_decision_agent import FEDDecisionAnalyzer
from app.ai.agents.cpi_decision_agent import CPIDecisionAnalyzer
from app.ai.agents.nfp_decision_agent import NFPDecisionAnalyzer
from app.ai.agents.social_media_agent import SocialMediaPostAnalyzer
from app.config import AppConfig

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.mark.parametrize(
    "cls",
    [
        FEDDecisionAnalyzer,
        CPIDecisionAnalyzer,
        NFPDecisionAnalyzer,
        SocialMediaPostAnalyzer,
    ],
)
async def test_all_schemas_use_one_http_request(cls, mocker, monkeypatch):
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        answers = {}
        for name, question in payload["questions"].items():
            if question["type"] == "noul":
                answers[name] = {"type": "noul", "noul": 0.995}
            else:
                options = list(question["criteria"])
                choice = options[0]
                answers[name] = {
                    "type": "choice",
                    "choice": choice,
                    "confidence": 0.99,
                    "probabilities": {
                        option: 1.0 if option == choice else 0.0 for option in options
                    },
                }
        return httpx2.Response(
            200,
            json={
                "model": "jev-test",
                "answers": answers,
                "usage": {"input_tokens": 10, "output_tokens": 1},
            },
        )

    def create_client(**kwargs):
        return AsyncTypeSafeClient(
            api_key="offline-test-key",
            transport=httpx2.MockTransport(respond),
            **kwargs,
        )

    mocker.patch("app.ai.jev_analyzer.AsyncTypeSafeClient", side_effect=create_client)
    monkeypatch.setattr(AppConfig, "JEV_MODEL", "typesafe:jev-1.13.0")
    monkeypatch.setattr(AppConfig, "JEV_CONFIDENCE_THRESHOLD", 0.85)
    analyzer = cls()
    try:
        result = await analyzer.analyze_content("Test release")
        assert not isinstance(result, cls.failure_type)
        assert len(requests) == 1
        assert set(requests[0]["questions"]) == set(cls.schema.model_fields)
        assert requests[0]["model"] == "jev-1.13.0"
    finally:
        await analyzer.aclose()


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_sdk_does_not_retry_http_errors(status, mocker):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx2.Response(status, json={"detail": "unavailable"})

    def create_client(**kwargs):
        return AsyncTypeSafeClient(
            api_key="offline-test-key",
            transport=httpx2.MockTransport(respond),
            **kwargs,
        )

    mocker.patch("app.ai.jev_analyzer.AsyncTypeSafeClient", side_effect=create_client)
    analyzer = FEDDecisionAnalyzer()
    try:
        assert isinstance(
            await analyzer.analyze_content("Test release"), analyzer.failure_type
        )
        assert len(requests) == 1
    finally:
        await analyzer.aclose()
