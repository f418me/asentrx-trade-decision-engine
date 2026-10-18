import pytest
import logfire
from pydantic_ai import Agent

from app.utils import logger_config

pytestmark = pytest.mark.unit


def test_logfire_configuration_supports_current_pydantic_ai(monkeypatch, mocker):
    configure = logfire.configure
    monkeypatch.setenv("LOGFIRE_TOKEN", "offline-test")
    monkeypatch.setattr(logger_config, "_logging_configured", False)
    mocker.patch.object(
        logfire,
        "configure",
        side_effect=lambda **kwargs: configure(send_to_logfire=False),
    )
    instrument = mocker.spy(Agent, "instrument_all")
    try:
        logger_config.configure_logging()
        instrument.assert_called_once_with()
    finally:
        Agent.instrument_all(False)
