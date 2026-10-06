# Application entrypoint: loads configuration, sets up DB, and runs polling.
import os
import sys
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from core.db import init_db
from core.logger import setup_logger
from modules.listener import register_listener

logger = setup_logger("main")

def main() -> None:
    """Bootstraps the database and starts the Telegram long-polling loop."""
    # Load secrets and environment parameters from .env
    load_dotenv()

    # Initialize SQLite database schema
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        sys.exit(1)

    # Validate bot token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Missing TELEGRAM_BOT_TOKEN in .env file.")
        sys.exit(1)

    # Build Telegram bot application
    app = ApplicationBuilder().token(token).build()

    # Register passive message logging handler
    register_listener(app)

    logger.info("Bot is active and listening via long-polling...")
    # Long-polling respects strict dorm firewalls and handles SIGINT/SIGTERM cleanly
    app.run_polling()

if __name__ == "__main__":
    main()
