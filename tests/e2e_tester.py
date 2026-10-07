import os
import sys
import asyncio
from dotenv import load_dotenv
from telegram import Bot

async def main():
    """
    Automated E2E Test Runner
    This script acts as a user in the test group, sending commands via the Test Runner Bot
    to verify the Main/Dev Bot processes them correctly.
    """
    load_dotenv()
    
    # Load configuration
    runner_token = os.getenv("TEST_RUNNER_BOT_TOKEN")
    chat_id = os.getenv("TEST_GROUP_CHAT_ID")
    
    if not runner_token or not chat_id:
        print("Error: TEST_RUNNER_BOT_TOKEN or TEST_GROUP_CHAT_ID not found in .env")
        sys.exit(1)

    # Initialize the Test Runner Bot client
    bot = Bot(token=runner_token)
    
    # Simulate a user tagging the development bot
    # We use the development bot's username so it picks up the message in the group
    message = "@SketchyIntelligenceTestBot /ping"
    
    print(f"Sending test message to group {chat_id}...")
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        print("Success! The test runner sent the message.")
        print("Check if the development bot processed it and replied in the Telegram group.")
    except Exception as e:
        print(f"Failed to send message: {e}")

if __name__ == "__main__":
    asyncio.run(main())
