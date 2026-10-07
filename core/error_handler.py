# Global error handling module for uncaught Telegram handler exceptions
from telegram.ext import ContextTypes
from core.logger import setup_logger

logger = setup_logger("error_handler")

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs full exception stack trace for any unhandled errors in Telegram loop."""
    logger.error(
        f"Unhandled exception while processing update {update}: {context.error}",
        exc_info=context.error,
    )
