"""Best-effort trade alerts via a channel-specific Slack incoming webhook."""

import logging
from urllib.parse import urlsplit

import requests

from app.config import AppConfig
from app.utils.logger_config import APP_LOGGER_NAME
from app.utils.observability import logfire_info, logfire_warning

logger = logging.getLogger(f"{APP_LOGGER_NAME}.SlackNotifier")


class SlackNotifier:
    def __init__(self):
        self.webhook_url = AppConfig.SLACK_WEBHOOK_URL.strip()
        self.enabled = AppConfig.SLACK_NOTIFICATIONS_ENABLED
        if not self.enabled:
            logger.info("Slack notifications are disabled.")
            return
        try:
            url = urlsplit(self.webhook_url)
            valid = (
                url.scheme == "https"
                and url.netloc in ("hooks.slack.com", "hooks.slack-gov.com")
                and url.path.startswith("/services/")
                and len(url.path.strip("/").split("/")) == 4
                and all(url.path.strip("/").split("/"))
                and not url.query and not url.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            self.enabled = False
            logger.warning("Slack disabled: SLACK_WEBHOOK_URL is missing or invalid.")
            logfire_warning("slack_notification_disabled", reason="invalid_configuration")

    def send_message(self, body: str, *, content_id: str | None = None) -> bool:
        if not self.enabled or not body.strip():
            return False
        try:
            # No retries or redirects: uncertain delivery must not duplicate alerts.
            response = requests.post(
                self.webhook_url,
                json={"text": body, "mrkdwn": False,
                      "unfurl_links": False, "unfurl_media": False},
                timeout=(2, 3),
                allow_redirects=False,
            )
            if response.status_code != 200 or response.text.strip() != "ok":
                logger.warning("Slack notification rejected (HTTP %s).", response.status_code)
                logfire_warning("slack_notification_failed", content_id=content_id,
                                status_code=response.status_code)
                return False
            logger.info("Slack notification sent for content_id=%s.", content_id)
            logfire_info("slack_notification_sent", content_id=content_id)
            return True
        except Exception as exc:
            # Exception strings/tracebacks can contain the secret webhook URL.
            logger.warning("Slack notification failed (%s).", type(exc).__name__)
            logfire_warning("slack_notification_failed", content_id=content_id,
                            error_type=type(exc).__name__)
            return False
