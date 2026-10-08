from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides a basic statistical summary to the user."""
    if update.effective_message:
        # Report basic bot activity in Ukrainian
        await update.effective_message.reply_text("Аналітика: система працює у штатному режимі.")

def register_analytics(app: Application) -> None:
    """Registers analytics command handlers in group 0."""
    app.add_handler(CommandHandler("stats", stats_command))

