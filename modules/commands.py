# Command handlers module: provides core user commands (/start, /help, /ping).
import os
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes
from core.database.languages import async_get_chat_language
from core.languages import DEFAULT_LANGUAGE, get_localized_string
from core.logger import setup_logger
from modules.access_control import is_admin
from modules.language import (
    START_CALLBACK_PREFIX,
    build_language_keyboard,
    format_start_text,
)

logger = setup_logger("commands")

# Concise one-sentence bot description registered with Telegram and shown on profiles
BOT_DESCRIPTION = (
    "An intelligent AI assistant running on Raspberry Pi, powered by Google Gemini for chat, news, and creative tools."
)
BOT_SHORT_DESCRIPTION = (
    "An intelligent AI assistant running on Raspberry Pi, powered by Google Gemini for chat, news, and creative tools."
)

START_TEXT = format_start_text("en")

PUBLIC_HELP_TEXT = get_localized_string("public_help_text", "en")
ADMIN_HELP_TEXT = PUBLIC_HELP_TEXT + "\n\n" + get_localized_string("admin_help_text", "en")
HELP_TEXT = PUBLIC_HELP_TEXT
PING_TEXT = get_localized_string("ping_text", "en")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends greeting in English and directly offers language selection buttons."""
    if update.effective_message:
        chat = update.effective_chat
        lang = await async_get_chat_language(chat.id) if chat else DEFAULT_LANGUAGE
        text = format_start_text(lang)
        keyboard = build_language_keyboard(lang, prefix=START_CALLBACK_PREFIX)
        await update.effective_message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the command directory in the chat's active language, displaying admin tools only to owner."""
    if update.effective_message:
        user = update.effective_user
        chat = update.effective_chat
        lang = await async_get_chat_language(chat.id) if chat else DEFAULT_LANGUAGE
        is_admin_user = user and is_admin(user.id)

        base_help = get_localized_string("public_help_text", lang)
        admin_help = get_localized_string("admin_help_text", lang) if is_admin_user else ""
        text = f"{base_help}{admin_help}"

        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies immediately in the chat's active language to verify the event loop is responsive."""
    if update.effective_message:
        chat = update.effective_chat
        lang = await async_get_chat_language(chat.id) if chat else DEFAULT_LANGUAGE
        text = get_localized_string("ping_text", lang)
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )


async def chat_member_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcomes group or supergroup chats in English when the bot is newly added."""
    result = update.my_chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    was_member = old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
    is_member = new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
    if not was_member and is_member:
        chat = update.effective_chat
        if chat and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            lang = await async_get_chat_language(chat.id)
            text = format_start_text(lang)
            keyboard = build_language_keyboard(lang, prefix=START_CALLBACK_PREFIX)
            await context.bot.send_message(
                chat_id=chat.id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )


def register_commands(app: Application) -> None:
    """Registers standard commands in the default handler group (group 0)."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(ChatMemberHandler(chat_member_update_handler, ChatMemberHandler.MY_CHAT_MEMBER))


# Command directory for general users (public scope in universal English)
PUBLIC_BOT_COMMANDS = [
    BotCommand("start", "Start interaction and view greeting"),
    BotCommand("help", "Show command guide and capabilities"),
    BotCommand("ping", "Check bot latency and responsiveness"),
    BotCommand("news", "Get latest news briefing with Google Search"),
    BotCommand("roast", "Friendly comedy roast of a chat member"),
    BotCommand("meme", "Generate an AI meme or image"),
    BotCommand("persona", "Select bot personality style"),
    BotCommand("lang", "Choose chat communication language"),
]
BOT_COMMANDS = PUBLIC_BOT_COMMANDS

# Extended command directory for the owner (private chat scope in universal English)
ADMIN_BOT_COMMANDS = PUBLIC_BOT_COMMANDS + [
    BotCommand("stats", "Gemini token usage and cost metrics"),
    BotCommand("access", "List access requests and whitelist status"),
    BotCommand("approve", "Approve access for a user ID or group"),
    BotCommand("reject", "Revoke or reject access for an ID"),
    BotCommand("switch_reaction", "Toggle automatic emoji reactions for chat"),
]



async def set_bot_commands(app: Application) -> None:
    """Registers commands with Telegram: public commands for all users, admin commands scoped to owner."""
    try:
        # Register bot profile description and empty-chat guidance with Telegram
        await app.bot.set_my_description(BOT_DESCRIPTION)
        await app.bot.set_my_short_description(BOT_SHORT_DESCRIPTION)

        # Default scope for all regular users
        await app.bot.set_my_commands(PUBLIC_BOT_COMMANDS, scope=BotCommandScopeDefault())

        # Scoped exclusively to the bot administrator's private chat
        admin_id_str = os.getenv("ADMIN_CHAT_ID")
        if admin_id_str:
            try:
                admin_id = int(admin_id_str.strip())
                await app.bot.set_my_commands(
                    ADMIN_BOT_COMMANDS,
                    scope=BotCommandScopeChat(chat_id=admin_id),
                )
            except ValueError:
                pass
        logger.info("Bot commands and descriptions registered with Telegram.")
    except Exception as exc:
        logger.warning(f"Could not register autocomplete commands or description with Telegram: {exc}")



