# Application bootstrap for the Telegram bot
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from core.logger import setup_logger

# Load environment configuration
load_dotenv()
logger = setup_logger("main")

def main() -> None:
    """Initializes and runs the Telegram bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("Missing TELEGRAM_BOT_TOKEN in .env")
        return
    app = ApplicationBuilder().token(token).build()
    logger.info("Bot started and listening...")
    app.run_polling()

if __name__ == "__main__":
    main()
