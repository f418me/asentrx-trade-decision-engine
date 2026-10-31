import logging
import json

import logfire

from app.config import AppConfig
from app.utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.observability")


def trade_outcome(*, content_id, outcome, reason_code, reason, **attributes):
    """One searchable decision summary; telemetry must never affect trading."""
    fields = dict(content_id=content_id, outcome=outcome, reason_code=reason_code,
                  reason=reason, **attributes)
    logger.info("trade_outcome %s", json.dumps(fields, default=str))
    try:
        logfire_info("trade_outcome", **fields)
    except Exception:
        logger.warning("Could not export trade_outcome to Logfire.")


def logfire_info(event: str, **attributes):
    if not AppConfig.LOGFIRE_TOKEN:
        return
    logfire.info(event, **attributes)


def logfire_warning(event: str, **attributes):
    if not AppConfig.LOGFIRE_TOKEN:
        return
    logfire.warning(event, **attributes)


def logfire_error(event: str, **attributes):
    if not AppConfig.LOGFIRE_TOKEN:
        return
    logfire.error(event, **attributes)
