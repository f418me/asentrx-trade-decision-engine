import logging

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
    return SlackNotifier()


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
