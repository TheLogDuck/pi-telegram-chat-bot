# Command handlers module: provides core user commands (/start, /help, /ping).
import os
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.database.languages import async_get_chat_language
from core.languages import get_localized_string
from core.logger import setup_logger
from modules.access_control import is_admin


logger = setup_logger("commands")

# Predefined response strings kept as constants to avoid string reallocations
START_TEXT = (
    "<b>Вітаю!</b> Я ваш Telegram-бот на базі Raspberry Pi.\n\n"
    "Я підтримую інтелектуальне спілкування за допомогою Google Gemini AI.\n"
    "У групах звертайтеся до мене через тег (наприклад, <code>@username</code>) або через відповідь (reply).\n"
    "Введіть <code>/help</code>, щоб переглянути список доступних команд."
)

PUBLIC_HELP_TEXT = (
    "<b>Довідка щодо команд та можливостей бота:</b>\n\n"
    "<b>Основні команди:</b>\n"
    "• <code>/start</code> — Початок взаємодії та коротке привітання.\n"
    "• <code>/help</code> — Переглянути цей докладний довідник команд.\n"
    "• <code>/ping</code> — Перевірити доступність та час відповіді бота на Raspberry Pi.\n\n"
    "<b>Інтелектуальні функції (Gemini AI):</b>\n"
    "• <code>/news [тема]</code> — Свіжий дайджест актуальних новин із пошуком Google.\n"
    "  <i>Приклад:</i> <code>/news</code> (головні події) або <code>/news космос</code>.\n"
    "• <code>/roast [@користувач]</code> — Дружня стендап-прожарка учасника на основі його повідомлень.\n"
    "  <i>Використання:</i> вкажіть тег (<code>/roast @username</code>) або надішліть у відповідь на повідомлення.\n"
    "• <code>/meme [опис]</code> — Генерація зображення або мему через ШІ (Nano Banana).\n"
    "  <i>Приклад:</i> <code>/meme кіт програміст лагодить сервер</code>.\n"
    "• <code>/persona</code> — Обрати стиль/персону спілкування бота (стандартний або мем-лорд).\n"
    "• <code>/lang</code> — Обрати мову спілкування бота для цього чату (UA, RU, EN, DE).\n"
    "• <b>Спілкування з ШІ:</b>\n"
    "  В особистих чатах пишіть будь-що напряму, а в групах — згадуйте через тег або reply."
)

ADMIN_HELP_TEXT = (
    PUBLIC_HELP_TEXT + "\n\n"
    "<b>Administration:</b>\n"
    "• <code>/access</code> — View approved access grants.\n"
    "• <code>/approve [id]</code> — Approve access for a user or group.\n"
    "• <code>/reject [id]</code> — Revoke access for a user or group.\n"
    "• <code>/stats</code> — Detailed Gemini token usage and cost metrics.\n"
    "• <code>/switch_reaction [id]</code> — Toggle bot emotional reactions for chat."
)


HELP_TEXT = PUBLIC_HELP_TEXT
PING_TEXT = "<b>Понг!</b> Бот активний і працює на Raspberry Pi."


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting when /start is issued in the chat's active language."""
    if update.effective_message:
        chat = update.effective_chat
        lang = await async_get_chat_language(chat.id) if chat else "uk"
        text = get_localized_string("start_text", lang)
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the command directory in the chat's active language, displaying admin tools only to owner."""
    if update.effective_message:
        user = update.effective_user
        chat = update.effective_chat
        lang = await async_get_chat_language(chat.id) if chat else "uk"
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
        lang = await async_get_chat_language(chat.id) if chat else "uk"
        text = get_localized_string("ping_text", lang)
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )


def register_commands(app: Application) -> None:
    """Registers standard commands in the default handler group (group 0)."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))


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
        logger.info("Bot commands registered with Telegram autocomplete menu.")
    except Exception as exc:
        logger.warning(f"Could not register autocomplete commands with Telegram: {exc}")



