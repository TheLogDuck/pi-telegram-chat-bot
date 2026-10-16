# Conversational module: handles AI dialogue with Google Gemini.
# Enforces the rule that the bot in groups speaks ONLY when tagged or replied to.
import re
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from core.database.languages import async_get_chat_language
from core.database.personas import async_get_user_persona
from core.languages import get_localized_string
from core.llm import generate_response
from core.logger import setup_logger
from core.rate_limiter import get_rate_limiter
from modules.analytics import stats_command
from modules.commands import help_command, ping_command
from modules.intent import IntentResult, IntentType, detect_intent
from modules.language import language_command
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


async def _dispatch_intent(
    intent_result: IntentResult,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Dispatches recognized command intents to their dedicated handler modules.

    Uses pattern matching to cleanly route intents with specific arguments.
    Returns True if an intent was handled, or False to fall through to Gemini conversational AI.
    """
    match intent_result.intent:
        case IntentType.PING:
            await ping_command(update, context)
        case IntentType.HELP:
            await help_command(update, context)
        case IntentType.STATS:
            await stats_command(update, context)
        case IntentType.NEWS:
            await news_command(update, context, topic=intent_result.topic)
        case IntentType.ROAST:
            await roast_command(update, context, target_user=intent_result.target_user)
        case IntentType.MEME:
            await meme_command(update, context, prompt=intent_result.topic)
        case IntentType.PERSONA:
            await persona_command(update, context)
        case IntentType.LANGUAGE:
            await language_command(update, context)
        case _:
            # Unmatched or general chat intent falls through to open-ended dialogue
            return False
    return True


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

    # If the user only tagged the bot without asking anything, greet them in chat's language
    if not cleaned_prompt:
        lang = await async_get_chat_language(chat.id)
        tag_text = get_localized_string("empty_tag_prompt", lang)
        await message.reply_text(
            tag_text,
            parse_mode=ParseMode.HTML,
        )
        return

    # Extract user ID and enforce per-user prompt cooldown
    user_id = message.from_user.id if message.from_user and isinstance(message.from_user.id, int) else None
    limiter = get_rate_limiter()
    if user_id:
        allowed, remaining = limiter.check_user_cooldown(user_id)
        if not allowed:
            lang = await async_get_chat_language(chat.id)
            notice = get_localized_string("rate_limit_user", lang)
            await message.reply_text(notice)
            return

    # Check for natural language or slash command intents and dispatch if recognized
    intent_result = detect_intent(cleaned_prompt)
    if await _dispatch_intent(intent_result, update, context):
        return

    # Enforce maximum concurrent AI generations per chat
    chat_id = chat.id if isinstance(chat.id, int) else 0
    if chat_id and not limiter.acquire_chat_slot(chat_id):
        lang = await async_get_chat_language(chat_id)
        notice = get_localized_string("rate_limit_chat", lang)
        await message.reply_text(notice)
        return

    try:
        # Inform the user that Gemini is processing their response
        try:
            await context.bot.send_chat_action(
                chat_id=chat.id,
                action=ChatAction.TYPING,
            )
        except Exception as exc:
            # Non-critical warning if typing action fails (e.g. transient network hiccup)
            logger.warning(f"Failed to send typing chat action: {exc}")

        # Extract caller user ID to look up their chosen persona and chat language
        persona_key = await async_get_user_persona(user_id) if user_id else "standard"
        language = await async_get_chat_language(chat.id)

        # Generate response via the non-blocking Gemini wrapper with user's persona and language
        result = await generate_response(
            cleaned_prompt,
            chat_id=chat.id,
            user_id=user_id,
            persona_key=persona_key,
            language=language,
        )
        if isinstance(result, tuple):
            ai_response, model_used = result
        else:
            ai_response, model_used = result, None

        # Reply directly to the user's message with rendered HTML and model attribution
        await send_formatted_reply(message, format_reply_with_model(ai_response, model_used))
    finally:
        if chat_id:
            limiter.release_chat_slot(chat_id)


def register_conversational(app: Application) -> None:
    """Registers the conversational message handler in group 0.

    Filters for plain text that is NOT a slash command, allowing slash commands
    to be handled by their dedicated CommandHandlers.
    """
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, conversational_chat_handler),
        group=0,
    )
