# Media handler module for photos, voice notes, and audio
from telegram import Update
from telegram.ext import ContextTypes

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming media attachments."""
    if update.message:
        # Acknowledge media receipt
        await update.message.reply_text("Media attachment received.")
