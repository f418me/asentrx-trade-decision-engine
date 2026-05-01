import logging
import secrets

from fastapi import Header, HTTPException, status

from app.config import AppConfig
from app.utils.logger_config import APP_LOGGER_NAME
from app.utils.observability import logfire_error, logfire_warning

logger = logging.getLogger(f"{APP_LOGGER_NAME}.security")


async def require_notify_auth(authorization: str | None = Header(default=None)):
    expected_token = AppConfig.NOTIFY_AUTH_TOKEN
    if not expected_token:
        logger.error("NOTIFY_AUTH_TOKEN is not configured. Rejecting notification request.")
        logfire_error("notify_auth_not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notification authentication is not configured.",
        )

    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Notification request rejected because Authorization bearer token is missing.")
        logfire_warning("notify_auth_missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing notification bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided_token, expected_token):
        logger.warning("Notification request rejected because Authorization bearer token is invalid.")
        logfire_warning("notify_auth_invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid notification bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
