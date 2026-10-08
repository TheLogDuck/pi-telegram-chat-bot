# Application entrypoint: loads configuration, sets up DB, and runs polling.
import os
import sys
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from core.db import init_db
from core.error_handler import global_error_handler
from core.logger import setup_logger
from modules.analytics import register_analytics
from modules.commands import register_commands, set_bot_commands
from modules.conversational import register_conversational
from modules.listener import register_listener
from modules.news import register_news
from modules.roast import register_roast


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

    # Build Telegram bot application with post_init hook for commands menu
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(set_bot_commands)
        .build()
    )


    # Register passive message logging handler (group -1)
    register_listener(app)

    # Register standard bot commands (group 0)
    register_commands(app)
    register_analytics(app)
    register_news(app)
    register_roast(app)

    # Register conversational AI chat handler (group 0)
    register_conversational(app)

    # Register global uncaught error handler
    app.add_error_handler(global_error_handler)



    logger.info("Bot is active and listening via long-polling...")
    # Long-polling respects strict dorm firewalls and handles SIGINT/SIGTERM cleanly
    app.run_polling()

if __name__ == "__main__":
    main()
