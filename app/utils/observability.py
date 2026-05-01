import logging

import logfire

from app.config import AppConfig
from app.utils.logger_config import APP_LOGGER_NAME

logger = logging.getLogger(f"{APP_LOGGER_NAME}.observability")


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
