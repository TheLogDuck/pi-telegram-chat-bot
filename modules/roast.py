# Roast module: generates context-aware humorous standup roasts of chat users.
# Supports slash command /roast <user>, message replies, and natural language triggers.
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes
from core.db import async_get_user_messages
from core.llm import generate_roast
from core.logger import setup_logger
from core.telegram_utils import is_bot_mentioned, send_formatted_reply

logger = setup_logger("roast")

NO_TARGET_HELP_TEXT = (
    "Кому саме влаштувати прожарку? Будь ласка, вкажіть користувача через @, "
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

    # If no target could be determined, explain how to use the command
    if not target_name:
        await send_formatted_reply(message, NO_TARGET_HELP_TEXT)
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
        limit=5,
    )

    # Step 3: Generate the humorous Ukrainian standup roast
    roast_text = await generate_roast(
        target_name=target_name,
        context_messages=context_messages,
    )

    # Step 4: Deliver the roast with formatted HTML and safe fallback
    await send_formatted_reply(message, roast_text)


def register_roast(app: Application) -> None:
    """Registers the /roast command handler in group 0."""
    app.add_handler(CommandHandler("roast", roast_command))
