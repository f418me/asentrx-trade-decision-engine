from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.trading.bitfinex_trader import BitfinexTrader
from app.trading.trader import Trader

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("after_seconds,submitted", [(1, True), (10, False), (11, False)])
def test_deadline_rechecked_after_quote(mocker, after_seconds, submitted):
    now = datetime(2026, 11, 25, 13, 34, 50, tzinfo=timezone.utc)
    clock = mocker.patch("app.trading.trader.datetime")
    clock.now.side_effect = [now, now + timedelta(seconds=after_seconds)]
    bfx = Mock(spec=BitfinexTrader)
    bfx.get_derivative_status.return_value = [["tBTCF0:USTF0", None, None, 100] + [None] * 11 + [100]]
    trader = Trader(bfx)
    result = trader.execute_order("tBTCF0:USTF0", .001, 3, .002,
                                 submit_before=now + timedelta(seconds=10))
    assert bfx.submit_order.called is submitted
    bfx.get_derivative_status.assert_called_once_with(symbol="tBTCF0:USTF0", timeout=(2, 3))
    if not submitted:
        assert result is None


def test_already_expired_never_fetches_quote():
    bfx = Mock(spec=BitfinexTrader)
    assert Trader(bfx).execute_order("tBTCF0:USTF0", .001, 3, .002,
        submit_before=datetime.now(timezone.utc) - timedelta(seconds=1)) is None
    bfx.get_derivative_status.assert_not_called()
    bfx.submit_order.assert_not_called()


def test_quote_timeout_is_forwarded(mocker):
    trader = BitfinexTrader.__new__(BitfinexTrader)
    trader.default_symbol = "tBTCF0:USTF0"
    get = mocker.patch("app.trading.bitfinex_trader.requests.get")
    trader.get_derivative_status(timeout=(2, 3))
    assert get.call_args.kwargs["timeout"] == (2, 3)
