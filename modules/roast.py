# Roast module: generates context-aware humorous standup roasts of chat users.
# Supports slash command /roast <user>, message replies, and natural language triggers.
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.database.languages import async_get_chat_language
from core.database.messages import async_get_user_messages
from core.database.personas import async_get_user_persona
from core.languages import get_localized_string
from core.llm import generate_roast
from core.logger import setup_logger
from core.telegram_utils import format_reply_with_model, is_bot_mentioned, send_formatted_reply

logger = setup_logger("roast")

NO_TARGET_HELP_TEXT = (
    "<b>Кому саме влаштувати прожарку?</b> Будь ласка, вкажіть користувача через <code>@</code>, "
    "наприклад: <code>/roast @username</code>, або надішліть команду у відповідь (reply) на його повідомлення."
)


async def roast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_user: Optional[str] = None,
) -> None:
    """Generates a context-aware standup roast of the specified target user."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # In group chats, verify the bot was tagged or specifically targeted
    bot_username = context.bot.username if context.bot else None
    bot_id = context.bot.id if context.bot else None

    # Step 1: Resolve target user and target user_id from various sources
    target_user_id: Optional[int] = None
    target_name: Optional[str] = target_user

    # If target not passed from intent matcher, check slash command arguments
    if not target_name and context.args:
        target_name = context.args[0]

    # If still not specified, check if user is replying to someone's message
    if not target_name and message.reply_to_message and message.reply_to_message.from_user:
        replied_user = message.reply_to_message.from_user
        target_user_id = replied_user.id
        target_name = replied_user.username or replied_user.first_name

    # If the target is self-referential (e.g. "roast me", "просмаж мене", "roaste mich")
    if target_name and target_name.lower().lstrip("@") in ("me", "мене", "меня", "mich", "mir"):
        if update.effective_user:
            target_user_id = update.effective_user.id
            target_name = update.effective_user.username or update.effective_user.first_name

    # If no target could be determined, explain how to use the command in chat's language
    if not target_name:
        chat_lang = await async_get_chat_language(chat.id)
        help_text = get_localized_string("no_target_roast_help", chat_lang)
        await message.reply_text(help_text, parse_mode=ParseMode.HTML)
        return

    # In group chats, ensure bot speaks only when tagged
    if not is_bot_mentioned(update, bot_username, bot_id):
        if message.text and f"@{bot_username}".lower() not in message.text.lower():
            pass

    # Send typing action to provide immediate feedback while Gemini generates roast
    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action=ChatAction.TYPING,
        )
    except Exception as exc:
        logger.warning(f"Failed to send typing chat action for roast: {exc}")

    # Step 2: Fetch recent messages from SQLite database to ground the roast in context
    context_messages = await async_get_user_messages(
        chat_id=chat.id,
        username=target_name,
        user_id=target_user_id,
        limit=10,
    )

    # If replying to a specific message, include that replied quote in context (e.g. for other bots or recent quotes)
    if message.reply_to_message:
        raw_text = message.reply_to_message.text or message.reply_to_message.caption
        if isinstance(raw_text, str) and raw_text.strip():
            replied_quote = raw_text.strip()
            if not context_messages or replied_quote not in context_messages:
                context_messages = [replied_quote] + (context_messages or [])

    # Step 3: Fetch caller persona, chat language, and generate standup roast
    caller_id = update.effective_user.id if update.effective_user else None
    persona_key = await async_get_user_persona(caller_id) if caller_id else "standard"
    chat_lang = await async_get_chat_language(chat.id)

    result = await generate_roast(
        target_name=target_name,
        context_messages=context_messages,
        chat_id=chat.id,
        user_id=caller_id,
        persona_key=persona_key,
        language=chat_lang,
    )
    if isinstance(result, tuple):
        roast_text, model_used = result
    else:
        roast_text, model_used = result, None

    # Step 4: Deliver the roast with formatted HTML and model attribution
    await send_formatted_reply(message, format_reply_with_model(roast_text, model_used))


def register_roast(app: Application) -> None:
    """Registers the /roast command handler in group 0."""
    app.add_handler(CommandHandler("roast", roast_command))
