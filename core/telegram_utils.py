# Telegram utility helpers for tag checking and token parsing.
# Shared across modules to avoid circular imports.
import re
from typing import Optional
from telegram import Update
from telegram.constants import ChatType


def is_bot_mentioned(
    update: Update,
    bot_username: Optional[str],
    bot_id: Optional[int],
) -> bool:
    """Checks whether the incoming message is directed at this bot.

    In private 1-on-1 chats, all messages are inherently directed to the bot.
    In group chats, the bot speaks ONLY if:
    1. The message text contains @bot_username or @@bot_username.
    2. The message is a direct reply to a previous message sent by the bot.
    """
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return False

    # In 1-on-1 private messages, user is always talking directly to the bot
    if chat.type == ChatType.PRIVATE:
        return True

    # Check if the message is a reply to one of the bot's messages
    if message.reply_to_message and message.reply_to_message.from_user:
        if bot_id is not None and message.reply_to_message.from_user.id == bot_id:
            return True

    # Check for text mentions of the bot's username (case-insensitive)
    if message.text and bot_username:
        normalized_name = bot_username.lstrip("@").lower()
        # Regex matches @username or @@username as a distinct token
        pattern = rf"@+{normalized_name}\b"
        if re.search(pattern, message.text, re.IGNORECASE):
            return True

    return False


def clean_bot_mention(text: str, bot_username: Optional[str]) -> str:
    """Removes bot mention tags (@username or @@username) from message text."""
    if not text:
        return ""

    if not bot_username:
        return text.strip()

    normalized_name = bot_username.lstrip("@")
    # Strip any occurrences of @username or @@username
    pattern = rf"@+{normalized_name}\b"
    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return cleaned.strip()
