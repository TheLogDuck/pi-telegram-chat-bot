# Listener module for intercepting incoming messages
from telegram import Update
from telegram.ext import ContextTypes

async def message_listener(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles raw incoming text messages."""
    if not update.message or not update.message.text:
        return
    # Process or log raw message text
    user_text = update.message.text
    # Handler logic can inspect or dispatch based on text
