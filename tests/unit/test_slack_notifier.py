import logging
import threading
import asyncio

import pytest
import requests

from app.config import AppConfig
from app.utils.slack_notifier import SlackNotifier

pytestmark = pytest.mark.unit
URL = "https://hooks.slack.com/services/TEST/CHANNEL/secret"


@pytest.fixture
def notifier(monkeypatch):
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(AppConfig, "SLACK_WEBHOOK_URL", URL)
    instance = SlackNotifier()
    yield instance
    instance.close()


def test_slack_success(notifier, mocker):
    post = mocker.patch("app.utils.slack_notifier.requests.post",
                        return_value=mocker.Mock(status_code=200, text="ok"))
    event = mocker.patch("app.utils.slack_notifier.logfire_info")
    assert notifier.send_message("Trade submitted", content_id="event-1")
    post.assert_called_once_with(
        URL, json={"text": "Trade submitted", "mrkdwn": False,
                   "unfurl_links": False, "unfurl_media": False},
        timeout=(2, 3), allow_redirects=False,
    )
    event.assert_called_once_with("slack_notification_sent", content_id="event-1")


@pytest.mark.parametrize("status,text", [(200, "invalid_payload"), (403, "forbidden"),
                                        (429, "rate_limited"), (500, "error"), (302, "")])
def test_slack_rejection_no_retry(notifier, mocker, status, text):
    post = mocker.patch("app.utils.slack_notifier.requests.post",
                        return_value=mocker.Mock(status_code=status, text=text))
    assert not notifier.send_message("Trade")
    post.assert_called_once()


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError, RuntimeError])
def test_slack_failure_redacts_secret(notifier, mocker, caplog, exception):
    mocker.patch("app.utils.slack_notifier.requests.post", side_effect=exception(URL))
    event = mocker.patch("app.utils.slack_notifier.logfire_warning")
    with caplog.at_level(logging.WARNING):
        assert not notifier.send_message("Trade", content_id="event-1")
    assert URL not in caplog.text
    assert URL not in str(event.call_args)
    event.assert_called_once_with("slack_notification_failed", content_id="event-1",
                                  error_type=exception.__name__)


@pytest.mark.parametrize("url", ["", "http://hooks.slack.com/services/A/B/C",
                                "https://example.com/services/A/B/C",
                                "https://hooks.slack.com/services/A/B/C?secret=x"])
def test_invalid_configuration_does_not_send(monkeypatch, mocker, url):
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(AppConfig, "SLACK_WEBHOOK_URL", url)
    post = mocker.patch("app.utils.slack_notifier.requests.post")
    assert not SlackNotifier().send_message("Trade")
    post.assert_not_called()


def test_disabled_and_empty_messages(notifier, mocker, monkeypatch):
    post = mocker.patch("app.utils.slack_notifier.requests.post")
    assert not notifier.send_message(" ")
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", False)
    assert not SlackNotifier().send_message("Trade")
    post.assert_not_called()


@pytest.mark.parametrize("failure", [False, True])
def test_telemetry_failure_preserves_delivery_result(notifier, mocker, failure):
    post = mocker.patch("app.utils.slack_notifier.requests.post",
                        return_value=mocker.Mock(status_code=200, text="ok"))
    if failure:
        post.side_effect = requests.Timeout("secret")
    mocker.patch("app.utils.slack_notifier.logfire_info", side_effect=RuntimeError("offline"))
    mocker.patch("app.utils.slack_notifier.logfire_warning", side_effect=RuntimeError("offline"))
    assert notifier.send_message("Trade") is (not failure)


@pytest.mark.asyncio
async def test_slow_slack_does_not_block_event_loop(notifier, mocker):
    entered, release = threading.Event(), threading.Event()
    threads = []
    def slow_post(*args, **kwargs):
        threads.append(threading.get_ident())
        entered.set()
        release.wait(timeout=2)
        return mocker.Mock(status_code=200, text="ok")
    mocker.patch("app.utils.slack_notifier.requests.post", side_effect=slow_post)
    try:
        assert notifier.enqueue_message("Trade", content_id="test")
        assert await asyncio.to_thread(entered.wait, 1)
        await asyncio.wait_for(asyncio.sleep(0), timeout=0.2)
        assert not release.is_set()
        assert threads == [notifier._worker.ident]
        assert threads[0] != threading.get_ident()
    finally:
        release.set()
        await asyncio.to_thread(notifier.close)
    assert not notifier._worker.is_alive()
    assert not notifier.enqueue_message("After shutdown")


def test_full_queue_drops_without_waiting(notifier, mocker):
    # Simulate a busy worker, without starting a background thread.
    notifier._worker = mocker.Mock()
    for _ in range(100):
        assert notifier.enqueue_message("Trade")
    assert not notifier.enqueue_message("Overflow")


def test_worker_start_failure_can_recover(notifier, mocker):
    worker = mocker.Mock()
    worker.start.side_effect = [RuntimeError("thread unavailable"), None]
    mocker.patch("app.utils.slack_notifier.threading.Thread", return_value=worker)
    assert not notifier.enqueue_message("First")
    assert notifier._worker is None
    assert notifier._queue.empty()
    assert notifier.enqueue_message("Retry")
    assert notifier._worker is worker
    notifier.close()
    worker.join.assert_called_once_with(timeout=5)


def test_invalid_config_survives_telemetry_failure(monkeypatch, mocker):
    monkeypatch.setattr(AppConfig, "SLACK_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(AppConfig, "SLACK_WEBHOOK_URL", "")
    mocker.patch("app.utils.slack_notifier.logfire_warning", side_effect=RuntimeError("offline"))
    assert not SlackNotifier().enabled
