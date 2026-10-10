# Conversational module: handles AI dialogue with Google Gemini.
# Enforces the rule that the bot in groups speaks ONLY when tagged or replied to.
import re
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from core.database.personas import async_get_user_persona
from core.llm import generate_response
from core.logger import setup_logger
from modules.analytics import stats_command
from modules.commands import help_command, ping_command
from modules.intent import IntentType, detect_intent
from modules.news import news_command
from modules.roast import roast_command
from modules.meme import meme_command
from modules.persona import persona_command

logger = setup_logger("conversational")

# Prompt returned when the user tags the bot without any query
EMPTY_TAG_PROMPT = (
    "<b>Привіт!</b> Чим я можу вам допомогти?\n"
    "Напишіть своє запитання або введіть <code>/help</code> для перегляду списку команд."
)


from core.telegram_utils import (
    clean_bot_mention,
    format_reply_with_model,
    is_bot_mentioned,
    send_formatted_reply,
)


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
        await message.reply_text(
            EMPTY_TAG_PROMPT,
            parse_mode=ParseMode.HTML,
        )
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
    elif intent_result.intent == IntentType.NEWS:
        await news_command(update, context, topic=intent_result.topic)
        return
    elif intent_result.intent == IntentType.ROAST:
        await roast_command(update, context, target_user=intent_result.target_user)
        return
    elif intent_result.intent == IntentType.MEME:
        await meme_command(update, context, prompt=intent_result.topic)
        return
    elif intent_result.intent == IntentType.PERSONA:
        await persona_command(update, context)
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

    # Extract caller user ID to look up their chosen persona
    user_id = message.from_user.id if message.from_user else None
    persona_key = await async_get_user_persona(user_id) if user_id else "standard"

    # Generate response via the non-blocking Gemini wrapper with user's persona
    result = await generate_response(
        cleaned_prompt,
        chat_id=chat.id,
        user_id=user_id,
        persona_key=persona_key,
    )
    if isinstance(result, tuple):
        ai_response, model_used = result
    else:
        ai_response, model_used = result, None

    # Reply directly to the user's message with rendered HTML and model attribution
    await send_formatted_reply(message, format_reply_with_model(ai_response, model_used))


def register_conversational(app: Application) -> None:
    """Registers the conversational message handler in group 0.

    Filters for plain text that is NOT a slash command, allowing slash commands
    to be handled by their dedicated CommandHandlers.
    """
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, conversational_chat_handler),
        group=0,
    )
