# Command handlers module: provides core user commands (/start, /help, /ping).
import os
from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.logger import setup_logger
from modules.auth import is_admin


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
    "• <code>/persona</code> — Обрати стиль/персону спілкування бота (стандартний або токсичний цинік 18+).\n"
    "• <b>Спілкування з ШІ:</b>\n"
    "  В особистих чатах пишіть будь-що напряму, а в групах — згадуйте через тег або reply."
)

ADMIN_HELP_TEXT = (
    PUBLIC_HELP_TEXT + "\n\n"
    "<b>Адміністрування:</b>\n"
    "• <code>/access</code> — Список запитів та статусів доступу.\n"
    "• <code>/approve [id]</code> — Надати доступ користувачу або групі.\n"
    "• <code>/reject [id]</code> — Відхилити або відкликати доступ.\n"
    "• <code>/stats</code> — Детальна статистика токенів Gemini (Tier 1) та витрат."
)

HELP_TEXT = PUBLIC_HELP_TEXT
PING_TEXT = "<b>Понг!</b> Бот активний і працює на Raspberry Pi."


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting when /start is issued."""
    if update.effective_message:
        # Non-blocking async reply directly back to the source chat with HTML formatting
        await update.effective_message.reply_text(
            START_TEXT,
            parse_mode=ParseMode.HTML,
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the command directory when /help is issued, displaying admin tools only to owner."""
    if update.effective_message:
        user = update.effective_user
        text = ADMIN_HELP_TEXT if user and is_admin(user.id) else PUBLIC_HELP_TEXT
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
        )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies immediately to verify the event loop is responsive."""
    if update.effective_message:
        # Heartbeat check: zero disk or external API overhead
        await update.effective_message.reply_text(
            PING_TEXT,
            parse_mode=ParseMode.HTML,
        )


def register_commands(app: Application) -> None:
    """Registers standard commands in the default handler group (group 0)."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))


# Command directory for general users (public scope)
PUBLIC_BOT_COMMANDS = [
    BotCommand("start", "Почати взаємодію та переглянути привітання"),
    BotCommand("help", "Показати довідку щодо команд"),
    BotCommand("ping", "Перевірити доступність та час відповіді бота"),
    BotCommand("news", "Отримати дайджест актуальних новин"),
    BotCommand("roast", "Влаштувати дружній роаст користувача"),
    BotCommand("meme", "Згенерувати мем або зображення через ШІ"),
    BotCommand("persona", "Обрати стиль або персону спілкування"),
]
BOT_COMMANDS = PUBLIC_BOT_COMMANDS

# Extended command directory for the owner (private chat scope)
ADMIN_BOT_COMMANDS = PUBLIC_BOT_COMMANDS + [
    BotCommand("stats", "Статистика токенів Gemini та витрат"),
    BotCommand("access", "Список запитів та статусів доступу"),
    BotCommand("approve", "Схвалити доступ для ID або групи"),
    BotCommand("reject", "Відхилити або відкликати доступ"),
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



