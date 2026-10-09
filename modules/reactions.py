# Module managing AI-driven emotional reactions and the per-chat admin toggle.
import asyncio
from typing import Optional
from telegram import ReactionTypeEmoji, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core.db import (
    async_get_effective_persona,
    async_get_recent_chat_messages,
    async_is_reaction_enabled,
    async_toggle_reaction_enabled,
)
from core.llm import decide_message_reaction
from core.logger import setup_logger
from modules.auth import is_admin


logger = setup_logger("reactions")


async def switch_reaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles automatic emoji reactions for the current chat or target chat ID (admin only)."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    if not user or not chat or not message or not is_admin(user.id):
        return

    # Default to current chat; only override if an explicit numeric chat_id is provided
    target_chat_id = chat.id
    if context.args:
        first_arg = context.args[0].strip()
        # Ignore bot handle mentions (e.g. /switch_reaction @bot)
        if not first_arg.startswith("@"):
            try:
                target_chat_id = int(first_arg)
            except ValueError:
                target_chat_id = chat.id

    new_state = await async_toggle_reaction_enabled(target_chat_id)

    status_label = "УВІМКНЕНО" if new_state else "ВИМКНЕНО"
    await message.reply_text(
        f"<b>Емоційні реакції:</b> {status_label} для чату <code>{target_chat_id}</code>.",
        parse_mode=ParseMode.HTML,
    )


async def reaction_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Evaluates incoming text messages and sets an emoji reaction when appropriate."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not message.text or not chat or not user:
        return

    # Skip messages from bots or commands
    if user.is_bot or message.text.strip().startswith("/"):
        return

    # Fast check: skip immediately if reactions are turned off for this chat
    if not await async_is_reaction_enabled(chat.id):
        return

    # Fetch last 5 messages from SQLite for context

    history = await async_get_recent_chat_messages(
        chat_id=chat.id,
        limit=5,
        before_id=message.message_id,
    )
    persona_key = await async_get_effective_persona(chat.id, user.id)
    author_name = user.first_name or user.username

    emoji, _ = await decide_message_reaction(
        current_message=message.text,
        chat_history=history,
        persona_key=persona_key,
        author_name=author_name,
        chat_id=chat.id,
        user_id=user.id,
    )

    if emoji:
        try:
            await message.set_reaction([ReactionTypeEmoji(emoji)])
        except Exception as exc:
            logger.warning(f"Failed to set reaction {emoji} on message {message.message_id}: {exc}")


def register_reactions(app: Application) -> None:
    """Registers the /switch_reaction command and reaction message listener."""
    app.add_handler(CommandHandler("switch_reaction", switch_reaction_command), group=0)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, reaction_message_handler),
        group=1,
    )




