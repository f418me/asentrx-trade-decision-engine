"""Best-effort trade alerts via a channel-specific Slack incoming webhook."""

import logging
import queue
import threading
from urllib.parse import urlsplit

import requests

from app.config import AppConfig
from app.utils.logger_config import APP_LOGGER_NAME
from app.utils.observability import logfire_info, logfire_warning

logger = logging.getLogger(f"{APP_LOGGER_NAME}.SlackNotifier")


def _emit(level, event, **attributes):
    try:
        (logfire_info if level == "info" else logfire_warning)(event, **attributes)
    except Exception:
        logger.warning("Slack telemetry export failed.")


class SlackNotifier:
    def __init__(self):
        self._queue = queue.Queue(maxsize=100)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._worker = None
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
            _emit("warning", "slack_notification_disabled", reason="invalid_configuration")

    def enqueue_message(self, body: str, *, content_id: str | None = None) -> bool:
        """True means queued, not delivered. Never wait for Slack on a request."""
        if not self.enabled or not body.strip():
            return False
        with self._lock:
            if self._closed.is_set():
                return False
            try:
                if self._worker is None:
                    worker = threading.Thread(target=self._run, name="slack-alerts", daemon=True)
                    worker.start()
                    self._worker = worker
                self._queue.put_nowait((body, content_id))
                return True
            except (queue.Full, RuntimeError):
                logger.warning("Slack alert could not be queued.")
                _emit("warning", "slack_notification_dropped", content_id=content_id,
                      reason="queue_unavailable")
                return False

    def _run(self):
        while not self._closed.is_set():
            try:
                body, content_id = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.send_message(body, content_id=content_id)
            except Exception:
                logger.warning("Slack worker delivery failed.")
            finally:
                self._queue.task_done()

    def close(self):
        """Stop accepting alerts; bound shutdown even if Slack is unavailable."""
        with self._lock:
            self._closed.set()
            worker = self._worker
        if worker is not None:
            worker.join(timeout=5)
        dropped = 0
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            _emit("warning", "slack_notification_dropped", reason="shutdown", count=dropped)

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
                _emit("warning", "slack_notification_failed", content_id=content_id,
                                status_code=response.status_code)
                return False
            logger.info("Slack notification sent for content_id=%s.", content_id)
            _emit("info", "slack_notification_sent", content_id=content_id)
            return True
        except Exception as exc:
            # Exception strings/tracebacks can contain the secret webhook URL.
            logger.warning("Slack notification failed (%s).", type(exc).__name__)
            _emit("warning", "slack_notification_failed", content_id=content_id,
                            error_type=type(exc).__name__)
            return False
