from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides a basic statistical summary to the user."""
    if update.effective_message:
        # Report basic bot activity
        await update.effective_message.reply_text("Analytics: System operational.")

def register_analytics(app: Application) -> None:
    """Registers analytics command handlers in group 0."""
    app.add_handler(CommandHandler("stats", stats_command))

