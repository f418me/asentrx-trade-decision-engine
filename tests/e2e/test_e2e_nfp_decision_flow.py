import pytest

from app.models import NFPReportImpact

pytestmark = pytest.mark.e2e


def test_e2e_nfp_flow(test_app_client):
    client, mocks = test_app_client

    mocks["nfp_analyzer"].analyze_content.return_value = NFPReportImpact(
        impact_on_bitcoin="positive",
        confidence=0.92,
        reasoning="Cooler-than-expected labor report.",
        actual_report_summary="Payrolls and wages were soft.",
        actual_nonfarm_payrolls_k=5,
        actual_unemployment_rate=4.3,
        actual_average_hourly_earnings_mom=0.1,
        actual_average_hourly_earnings_yoy=3.1,
    )
    payload = {
        "type": "web-monitor",
        "url": "https://www.bls.gov/news.release/empsit.htm",
        "content-id": "bls-empsit-august-2026-released-2026-09-04",
        "content": "Employment Situation News Release\nTHE EMPLOYMENT SITUATION - AUGUST 2026\nTotal nonfarm payroll employment changed little in August (+5,000), and the unemployment rate was 4.3 percent.",
        "ip": "127.0.0.1",
    }

    response = client.post("/notify/web-monitor", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mocks["fed_analyzer"].analyze_content.assert_not_awaited()
    mocks["nfp_analyzer"].analyze_content.assert_awaited_once()
    mocks["trade_manager"].execute_trade_from_analysis.assert_called_once()
