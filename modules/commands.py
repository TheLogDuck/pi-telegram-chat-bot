# Command handlers module: provides core user commands (/start, /help, /ping).
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from core.logger import setup_logger


logger = setup_logger("commands")

# Predefined response strings kept as constants to avoid string reallocations
START_TEXT = (
    "Welcome! I am your Raspberry Pi Telegram Bot.\n\n"
    "I listen to group conversations and provide utilities.\n"
    "Type /help to see available commands."
)

HELP_TEXT = (
    "Available Commands:\n"
    "/start - Initialize interaction and view welcome message\n"
    "/help  - Display this command manual\n"
    "/ping  - Verify bot uptime and connection latency\n"
    "/stats - Show message activity statistics"
)

PING_TEXT = "Pong! Bot is active and running on Raspberry Pi."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting when /start is issued."""
    if update.effective_message:
        # Non-blocking async reply directly back to the source chat
        await update.effective_message.reply_text(START_TEXT)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the command directory when /help is issued."""
    if update.effective_message:
        # Uses constant string, avoiding heap allocation and CPU overhead
        await update.effective_message.reply_text(HELP_TEXT)

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
    BotCommand("start", "Initialize interaction and view welcome message"),
    BotCommand("help", "Display command manual"),
    BotCommand("ping", "Verify bot uptime and latency"),
    BotCommand("stats", "Show message activity statistics"),
]

async def set_bot_commands(app: Application) -> None:
    """Registers commands with Telegram so they appear when typing '/' in chat."""
    try:
        await app.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot commands registered with Telegram autocomplete menu.")
    except Exception as exc:
        # Prevent temporary network hiccups from blocking application boot
        logger.warning(f"Could not register autocomplete commands with Telegram: {exc}")


