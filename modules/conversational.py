# Conversational module: handles AI dialogue with Google Gemini.
# Enforces the rule that the bot in groups speaks ONLY when tagged or replied to.
import re
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from core.llm import generate_response
from core.logger import setup_logger
from modules.analytics import stats_command
from modules.commands import help_command, ping_command
from modules.intent import IntentType, detect_intent

logger = setup_logger("conversational")

# Prompt returned when the user tags the bot without any query
EMPTY_TAG_PROMPT = "Привіт! Чим я можу вам допомогти?"


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


async def conversational_chat_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handles incoming conversational messages, enforcing the tag-only rule."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not message.text or not chat:
        return

    # Extract bot identification details from context
    bot_username = context.bot.username if context.bot else None
    bot_id = context.bot.id if context.bot else None

    # Silently ignore untagged chatter in group chats to preserve chat privacy
    if not is_bot_mentioned(update, bot_username, bot_id):
        return

    # Remove the tag from the prompt so Gemini receives clean context
    cleaned_prompt = clean_bot_mention(message.text, bot_username)

    # If the user only tagged the bot without asking anything, greet them
    if not cleaned_prompt:
        await message.reply_text(EMPTY_TAG_PROMPT)
        return

    # Check for natural language or slash command intents
    intent_result = detect_intent(cleaned_prompt)

    # Route matched commands to their specialized handlers
    if intent_result.intent == IntentType.PING:
        await ping_command(update, context)
        return
    elif intent_result.intent == IntentType.HELP:
        await help_command(update, context)
        return
    elif intent_result.intent == IntentType.STATS:
        await stats_command(update, context)
        return

    # Inform the user that Gemini is processing their response
    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action=ChatAction.TYPING,
        )
    except Exception as exc:
        # Non-critical warning if typing action fails (e.g. transient network hiccup)
        logger.warning(f"Failed to send typing chat action: {exc}")

    # Generate response via the non-blocking Gemini wrapper
    ai_response = await generate_response(cleaned_prompt)

    # Reply directly to the user's message
    await message.reply_text(ai_response)


def register_conversational(app: Application) -> None:
    """Registers the conversational message handler in group 0.

    Filters for plain text that is NOT a slash command, allowing slash commands
    to be handled by their dedicated CommandHandlers.
    """
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, conversational_chat_handler),
        group=0,
    )
