# Application entrypoint: loads configuration, sets up DB, and runs polling.
import asyncio
import os
import sys
from dotenv import load_dotenv
from telegram.ext import Application, ApplicationBuilder
from core.db import async_cleanup_old_messages, init_db
from core.error_handler import global_error_handler
from core.logger import setup_logger
from modules.analytics import register_analytics
from modules.commands import register_commands, set_bot_commands
from modules.conversational import register_conversational
from modules.listener import register_listener
from modules.news import register_news
from modules.roast import register_roast
from modules.meme import register_meme
from modules.auth import register_auth
from modules.persona import register_persona


logger = setup_logger("main")


# Daily cleanup interval in seconds (24 hours)
CLEANUP_INTERVAL_SECONDS = 86400


async def periodic_cleanup_task(
    interval: int = CLEANUP_INTERVAL_SECONDS,
) -> None:
    """Runs database pruning periodically in the background (waits 24 hours before first run)."""
    while True:
        try:
            # Wait full interval before performing first cleanup
            await asyncio.sleep(interval)
            deleted = await async_cleanup_old_messages()
            if deleted > 0:
                logger.info(f"Scheduled maintenance pruned {deleted} old messages.")
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"Error during periodic message cleanup: {exc}")


async def on_startup(app: Application) -> None:
    """Post-initialization hook called once the event loop is active."""
    # Register autocomplete commands in Telegram UI
    await set_bot_commands(app)

    # Launch non-blocking periodic background cleanup and track in bot_data
    cleanup_task = asyncio.create_task(periodic_cleanup_task())
    app.bot_data["cleanup_task"] = cleanup_task


async def on_shutdown(app: Application) -> None:
    """Gracefully cancels background tasks upon shutdown or SIGINT."""
    task = app.bot_data.get("cleanup_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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

    # Build Telegram bot application with lifecycle hooks for commands and tasks
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )


    # Register passive message logging handler (group -2)
    register_listener(app)

    # Register authorization gatekeeper and admin callbacks (group -1)
    register_auth(app)

    # Register standard bot commands (group 0)
    register_commands(app)
    register_persona(app)
    register_analytics(app)
    register_news(app)
    register_roast(app)
    register_meme(app)

    # Register conversational AI chat handler (group 0)
    register_conversational(app)

    # Register global uncaught error handler
    app.add_error_handler(global_error_handler)



    logger.info("Bot is active and listening via long-polling...")
    # Long-polling respects strict dorm firewalls and handles SIGINT/SIGTERM cleanly
    app.run_polling()

if __name__ == "__main__":
    main()
