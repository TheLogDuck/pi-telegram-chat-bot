# Listener module to passively record incoming text messages into the database.
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from core.db import async_save_message
from core.logger import setup_logger

logger = setup_logger("listener")

async def passive_message_listener(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Silently logs incoming text messages into SQLite without responding."""
    if not update.effective_message or not update.effective_message.text:
        return

    # Extract user and chat metadata safely
    message = update.effective_message
    chat_id = update.effective_chat.id if update.effective_chat else 0
    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username if update.effective_user else None
    text = message.text

    # Telegram message timestamp formatted in ISO-8601
    timestamp = message.date.isoformat() if message.date else None

    try:
        # Non-blocking SQLite persistence
        await async_save_message(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            text=text,
            timestamp=timestamp,
        )
    except Exception as exc:
        # Prevent logging errors from crashing the bot
        logger.error(f"Failed to passively record message: {exc}")

def register_listener(app: Application) -> None:
    """Registers the passive logging handler in handler group -1.
    
    Handler group -1 runs before any standard command handlers (group 0)
    and does not block them.
    """
    app.add_handler(
        MessageHandler(filters.TEXT, passive_message_listener),
        group=-1,
    )
