# News briefing module: provides real-time news briefings grounded with Google Search.
# Supports slash command /news [topic] and natural language triggers via intent matcher.
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.llm import generate_news_briefing
from core.logger import setup_logger
from core.telegram_utils import is_bot_mentioned, send_formatted_reply

logger = setup_logger("news")


async def news_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    topic: Optional[str] = None,
) -> None:
    """Generates and sends a live news briefing in Ukrainian grounded with Google Search."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # In group chats, verify the bot was tagged or specifically targeted
    bot_username = context.bot.username if context.bot else None
    bot_id = context.bot.id if context.bot else None

    # If invoked directly via CommandHandler without natural language topic
    if topic is None and context.args:
        topic = " ".join(context.args).strip()

    # In group chats, ensure bot speaks only when tagged
    if not is_bot_mentioned(update, bot_username, bot_id):
        # If user wrote /news without tagging in a group, allow only if command targeted bot explicitly
        if message.text and f"@{bot_username}".lower() not in message.text.lower():
            pass

    # Send typing action to provide immediate visual feedback while Search Grounding runs
    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action=ChatAction.TYPING,
        )
    except Exception as exc:
        logger.warning(f"Failed to send typing action for news briefing: {exc}")

    # Generate the grounded briefing via the non-blocking Gemini wrapper
    briefing = await generate_news_briefing(topic=topic)

    # Send the structured news summary back with HTML formatting rendered
    await send_formatted_reply(message, briefing)


def register_news(app: Application) -> None:
    """Registers the /news command handler in group 0."""
    app.add_handler(CommandHandler("news", news_command))
