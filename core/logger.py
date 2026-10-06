# Core logging utility to standardize bot log output
import logging
import os

def setup_logger(name: str = "bot") -> logging.Logger:
    """Configures and returns a named logger instance."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, level, logging.INFO),
    )
    return logging.getLogger(name)
