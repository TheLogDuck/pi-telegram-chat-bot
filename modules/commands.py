# Command handlers module: provides core user commands (/start, /help, /ping).
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.logger import setup_logger


logger = setup_logger("commands")

# Predefined response strings kept as constants to avoid string reallocations
START_TEXT = (
    "Вітаю! Я ваш Telegram-бот на базі Raspberry Pi.\n\n"
    "Я підтримую спілкування за допомогою штучного інтелекту Gemini.\n"
    "У групах звертайтеся до мене через тег (наприклад, @username).\n"
    "Введіть /help, щоб переглянути список доступних команд."
)

HELP_TEXT = (
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
    "• <b>Спілкування з ШІ:</b>\n"
    "  В особистих чатах пишіть будь-що напряму, а в групах — згадуйте через тег або reply.\n\n"
    "<b>Адміністрування:</b>\n"
    "• <code>/stats</code> — Детальна статистика токенів Gemini (Tier 1), запитів та вартості (тільки для власника)."
)

PING_TEXT = "Понг! Бот активний і працює на Raspberry Pi."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting when /start is issued."""
    if update.effective_message:
        # Non-blocking async reply directly back to the source chat
        await update.effective_message.reply_text(START_TEXT)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the command directory when /help is issued."""
    if update.effective_message:
        # Uses constant string, avoiding heap allocation and CPU overhead
        await update.effective_message.reply_text(
            HELP_TEXT,
            parse_mode=ParseMode.HTML,
        )

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies immediately to verify the event loop is responsive."""
    if update.effective_message:
        # Heartbeat check: zero disk or external API overhead
        await update.effective_message.reply_text(PING_TEXT)

def register_commands(app: Application) -> None:
    """Registers standard commands in the default handler group (group 0)."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))

# Command directory used by Telegram client autocomplete menu
BOT_COMMANDS = [
    BotCommand("start", "Почати взаємодію та переглянути привітання"),
    BotCommand("help", "Показати довідку щодо команд"),
    BotCommand("ping", "Перевірити доступність та час відповіді бота"),
    BotCommand("stats", "Показати статистику активності"),
    BotCommand("news", "Отримати дайджест актуальних новин"),
    BotCommand("roast", "Влаштувати дружній роаст користувача"),
    BotCommand("meme", "Згенерувати мем або зображення через ШІ"),
]

async def set_bot_commands(app: Application) -> None:
    """Registers commands with Telegram so they appear when typing '/' in chat."""
    try:
        await app.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot commands registered with Telegram autocomplete menu.")
    except Exception as exc:
        # Prevent temporary network hiccups from blocking application boot
        logger.warning(f"Could not register autocomplete commands with Telegram: {exc}")


