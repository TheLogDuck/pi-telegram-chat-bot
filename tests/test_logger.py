# Unit tests for core logger configuration under hardware constraints
import logging
from core.logger import setup_logger

def test_setup_logger_returns_logger() -> None:
    """Verifies that setup_logger returns a configured named logger."""
    logger = setup_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"

def test_third_party_loggers_are_silenced() -> None:
    """Verifies that noisy third-party loggers are throttled to WARNING level."""
    setup_logger("test_check")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("telegram.ext").level == logging.WARNING


def test_setup_logger_respects_env_vars(monkeypatch) -> None:
    """Verifies that setup_logger respects environment variables like LOG_LEVEL."""
    import core.logger
    # Temporarily reset initialization flag for isolated unit testing
    monkeypatch.setattr(core.logger, "_LOGGING_INITIALIZED", False)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    logger = core.logger.setup_logger("debug_module")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG

