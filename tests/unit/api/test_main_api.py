import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import CPIReportImpact, FEDDecisionImpact, FailedFEDAnalysis, NFPReportImpact
from tests.conftest import TEST_NOTIFY_AUTH_HEADERS

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def mock_social_startup(mocker):
    mocker.patch('app.main.SocialMediaPostAnalyzer', autospec=True)


def test_web_monitor_notification_rejects_already_processed_url(mocker):
    mocker.patch('app.main.FEDDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.NFPDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
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
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        client.app.state.processed_content_ids.add(processed_url)
        response = client.post("/notify/web-monitor", json=payload, headers=TEST_NOTIFY_AUTH_HEADERS)

    assert response.status_code == 409
    assert "already processed" in response.json()["detail"]
    assert processed_url in client.app.state.processed_content_ids


def test_web_monitor_notification_rejects_already_processed_content_id(mocker):
    mocker.patch('app.main.FEDDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.NFPDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    dedup_key = "bls-empsit-august-2026-released-2026-09-04"
    payload = {
        "uuid": "test-uuid-processed-nfp",
        "type": "web-monitor",
        "url": "https://www.bls.gov/news.release/empsit.htm",
        "content-id": dedup_key,
        "content": "Employment Situation report content",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        client.app.state.processed_content_ids.add(dedup_key)
        response = client.post("/notify/web-monitor", json=payload, headers=TEST_NOTIFY_AUTH_HEADERS)

    assert response.status_code == 409
    assert "already processed" in response.json()["detail"]
    assert dedup_key in client.app.state.processed_content_ids


def test_web_monitor_notification_success_flow_adds_dedup_key_to_set(mocker):
    successful_analysis = FEDDecisionImpact(
        impact_on_bitcoin="positive",
        confidence=0.99,
        reasoning="Mocked positive impact",
        actual_fed_decision_summary="Mocked summary",
    )
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.aclose = AsyncMock()
    mock_analyzer_instance.analyze_content = AsyncMock(return_value=successful_analysis)
    mocker.patch('app.main.FEDDecisionAnalyzer', return_value=mock_analyzer_instance)
    mocker.patch('app.main.NFPDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
    mock_trade_manager_instance = MagicMock()
    mocker.patch('app.main.TradeDecisionManager', return_value=mock_trade_manager_instance)
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {
        "uuid": "test-uuid-123",
        "type": "web-monitor",
        "url": "http://test.com/unique-url-1",
        "content-id": "monetary20260916a",
        "content": "The FED decided to be very positive today.",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        client.app.state.processed_content_ids.clear()
        response = client.post("/notify/web-monitor", json=payload, headers=TEST_NOTIFY_AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Notification processed and trade logic triggered."}
    mock_analyzer_instance.analyze_content.assert_awaited_once()
    mock_trade_manager_instance.execute_trade_from_analysis.assert_called_once()
    assert payload["content-id"] in client.app.state.processed_content_ids


def test_web_monitor_notification_routes_bls_payload_to_nfp_analyzer(mocker):
    fed_analyzer = MagicMock()
    fed_analyzer.aclose = AsyncMock()
    fed_analyzer.analyze_content = AsyncMock()
    nfp_analyzer = MagicMock()
    nfp_analyzer.aclose = AsyncMock()
    nfp_analyzer.analyze_content = AsyncMock(return_value=NFPReportImpact(
        impact_on_bitcoin="positive",
        confidence=0.91,
        reasoning="Softer labor report than expected.",
        actual_report_summary="Payrolls came in soft with cooler wages.",
        actual_nonfarm_payrolls_k=5,
        actual_unemployment_rate=4.3,
        actual_average_hourly_earnings_mom=0.1,
        actual_average_hourly_earnings_yoy=3.1,
    ))
    trade_manager = MagicMock()

    mocker.patch('app.main.FEDDecisionAnalyzer', return_value=fed_analyzer)
    mocker.patch('app.main.NFPDecisionAnalyzer', return_value=nfp_analyzer)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.TradeDecisionManager', return_value=trade_manager)
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {
        "uuid": "test-uuid-nfp-route",
        "type": "web-monitor",
        "url": "https://www.bls.gov/news.release/empsit.htm",
        "content-id": "bls-empsit-august-2026-released-2026-09-04",
        "content": "Employment Situation News Release\nTHE EMPLOYMENT SITUATION - AUGUST 2026\nTotal nonfarm payroll employment changed little in August (+5,000), and the unemployment rate was 4.3 percent.",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        response = client.post("/notify/web-monitor", json=payload, headers=TEST_NOTIFY_AUTH_HEADERS)

    assert response.status_code == 200
    fed_analyzer.analyze_content.assert_not_awaited()
    nfp_analyzer.analyze_content.assert_awaited_once()
    trade_manager.execute_trade_from_analysis.assert_called_once()


def test_web_monitor_notification_routes_bls_cpi_payload_to_cpi_analyzer(mocker):
    fed_analyzer = MagicMock()
    fed_analyzer.aclose = AsyncMock()
    fed_analyzer.analyze_content = AsyncMock()
    nfp_analyzer = MagicMock()
    nfp_analyzer.aclose = AsyncMock()
    nfp_analyzer.analyze_content = AsyncMock()
    cpi_analyzer = MagicMock()
    cpi_analyzer.aclose = AsyncMock()
    cpi_analyzer.analyze_content = AsyncMock(return_value=CPIReportImpact(
        impact_on_bitcoin="negative",
        confidence=0.91,
        reasoning="Core CPI was hotter than expected.",
        actual_report_summary="Headline and core inflation surprised higher.",
        actual_headline_cpi_mom=0.3,
        actual_headline_cpi_yoy=3.5,
        actual_core_cpi_mom=0.3,
        actual_core_cpi_yoy=2.5,
    ))
    trade_manager = MagicMock()

    mocker.patch('app.main.FEDDecisionAnalyzer', return_value=fed_analyzer)
    mocker.patch('app.main.NFPDecisionAnalyzer', return_value=nfp_analyzer)
    mocker.patch('app.main.CPIDecisionAnalyzer', return_value=cpi_analyzer)
    mocker.patch('app.main.TradeDecisionManager', return_value=trade_manager)
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {
        "uuid": "test-uuid-cpi-route",
        "type": "web-monitor",
        "url": "https://www.bls.gov/news.release/cpi.htm",
        "content-id": "bls-cpi-august-2026-released-2026-09-11",
        "content": "Consumer Price Index News Release\nCONSUMER PRICE INDEX - AUGUST 2026\nThe Consumer Price Index for All Urban Consumers rose 0.3 percent in August. The index for all items less food and energy rose 0.3 percent.",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        response = client.post("/notify/web-monitor", json=payload, headers=TEST_NOTIFY_AUTH_HEADERS)

    assert response.status_code == 200
    fed_analyzer.analyze_content.assert_not_awaited()
    nfp_analyzer.analyze_content.assert_not_awaited()
    cpi_analyzer.analyze_content.assert_awaited_once()
    trade_manager.execute_trade_from_analysis.assert_called_once()


def test_web_monitor_notification_analyzer_fails_returns_200(mocker):
    failed_analysis = FailedFEDAnalysis(error_message="AI failed spectacularly")
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.aclose = AsyncMock()
    mock_analyzer_instance.analyze_content = AsyncMock(return_value=failed_analysis)
    mocker.patch('app.main.FEDDecisionAnalyzer', return_value=mock_analyzer_instance)
    mocker.patch('app.main.NFPDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    fail_url = "http://test.com/unique-url-fail"
    payload = {
        "uuid": "test-uuid-fail",
        "type": "web-monitor",
        "url": fail_url,
        "content": "bad content",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        client.app.state.processed_content_ids.clear()
        response = client.post("/notify/web-monitor", json=payload, headers=TEST_NOTIFY_AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "success_analysis_failed"
    assert "Analysis failed" in response.json()["message"]
    assert fail_url in client.app.state.processed_content_ids


def test_web_monitor_notification_rejects_missing_auth_token(mocker):
    mocker.patch('app.main.FEDDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.NFPDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {
        "uuid": "test-uuid-no-auth",
        "type": "web-monitor",
        "url": "http://test.com/no-auth",
        "content": "some content",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        response = client.post("/notify/web-monitor", json=payload)

    assert response.status_code == 401


def test_truth_social_notification_rejects_invalid_auth_token(mocker):
    mocker.patch('app.main.FEDDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.NFPDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.CPIDecisionAnalyzer', autospec=True)
    mocker.patch('app.main.TradeDecisionManager')
    mocker.patch('app.main.SmsNotifier')
    mocker.patch('app.main.Trader')
    mocker.patch('app.main.BitfinexTrader')

    payload = {
        "uuid": "test-uuid-bad-auth",
        "type": "truthsocial",
        "url": "https://truthsocial.com/@realDonaldTrump/1",
        "username": "realDonaldTrump",
        "content-id": "1",
        "content": "some content",
        "ip": "127.0.0.1",
    }

    with TestClient(app) as client:
        response = client.post(
            "/notify/truth-social",
            json=payload,
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 401
