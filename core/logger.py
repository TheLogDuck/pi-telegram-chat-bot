# Optimized logging module designed for Raspberry Pi hardware constraints
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

_LOGGING_INITIALIZED = False

# Maximum 2 MB per file, 2 backups: strict 6 MB disk ceiling for MicroSD safety
MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 2

def setup_logger(name: str = "bot") -> logging.Logger:
    """Configures and returns a named logger instance optimized for Pi storage."""
    global _LOGGING_INITIALIZED

    if not _LOGGING_INITIALIZED:
        log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Determine handlers from environment flags
        log_to_console = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
        log_to_file = os.getenv("LOG_TO_FILE", "false").lower() == "true"

        # Safety fallback: if both are disabled, keep console so logs are not lost
        if not log_to_console and not log_to_file:
            log_to_console = True

        # Console stream handler (captured by systemd when enabled)
        if log_to_console:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)

        # Rotating file handler: strict byte limits prevent SD card exhaustion
        if log_to_file:
            file_path = os.getenv("LOG_FILE_PATH", "bot.log")
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)


        # Suppress chatty third-party polling logs to reduce MicroSD write wear
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("telegram.ext").setLevel(logging.WARNING)

        _LOGGING_INITIALIZED = True

    return logging.getLogger(name)
