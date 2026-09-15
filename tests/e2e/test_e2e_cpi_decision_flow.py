import pytest

from app.models import CPIReportImpact

pytestmark = pytest.mark.e2e


def test_e2e_cpi_flow(test_app_client):
    client, mocks = test_app_client

    mocks["cpi_analyzer"].analyze_content.return_value = CPIReportImpact(
        impact_on_bitcoin="negative",
        confidence=0.92,
        reasoning="Core CPI was hotter than expected.",
        actual_report_summary="Headline and core CPI surprised higher.",
        actual_headline_cpi_mom=0.3,
        actual_headline_cpi_yoy=3.5,
        actual_core_cpi_mom=0.3,
        actual_core_cpi_yoy=2.5,
    )
    payload = {
        "type": "web-monitor",
        "url": "https://www.bls.gov/news.release/cpi.htm",
        "content-id": "bls-cpi-august-2026-released-2026-09-11",
        "content": "Consumer Price Index News Release\nCONSUMER PRICE INDEX - AUGUST 2026\nThe Consumer Price Index for All Urban Consumers rose 0.3 percent in August. The index for all items less food and energy rose 0.3 percent.",
        "ip": "127.0.0.1",
    }

    response = client.post("/notify/web-monitor", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mocks["fed_analyzer"].analyze_content.assert_not_awaited()
    mocks["nfp_analyzer"].analyze_content.assert_not_awaited()
    mocks["cpi_analyzer"].analyze_content.assert_awaited_once()
    mocks["trade_manager"].execute_trade_from_analysis.assert_called_once()
