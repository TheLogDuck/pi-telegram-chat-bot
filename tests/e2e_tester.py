# Automated End-to-End (E2E) Live Testing Suite.
# Simulates synthetic user interactions in the shared test group via the Test Runner Bot.
import asyncio
import os
import sys
from typing import List, Tuple
from dotenv import load_dotenv
from telegram import Bot

# Default target bot username in test group
DEFAULT_TARGET_BOT = "@SketchyIntelligenceTestBot"

# Test scenarios covering implemented features: tags, intents, Gemini dialogue, silence
TEST_SCENARIOS: List[Tuple[str, str, str]] = [
    (
        "Slash Command /ping",
        "{bot} /ping",
        "Expected: Quick reply with 'Понг! Бот активний і працює на Raspberry Pi.'",
    ),
    (
        "Natural Language Ukrainian Ping",
        "{bot} пінг",
        "Expected: Fast-path intent dispatch to ping_command in Ukrainian.",
    ),
    (
        "Natural Language Russian Ping",
        "{bot} пинг",
        "Expected: Russian trigger matching with ping_command dispatch.",
    ),
    (
        "Natural Language Help via Intent",
        "{bot} допомога",
        "Expected: Ukrainian command manual displayed.",
    ),
    (
        "Natural Language Stats via Intent",
        "{bot} статистика",
        "Expected: Analytics status report in Ukrainian.",
    ),
    (
        "Conversational AI Dialogue (Ukrainian query)",
        "{bot} поясни одним коротким реченням, що таке квантовий комп'ютер?",
        "Expected: Typing action followed by Gemini response in Ukrainian.",
    ),
    (
        "Conversational AI Dialogue (Russian query -> Ukrainian answer)",
        "{bot} объясни одним коротким предложением, как работает гравитация?",
        "Expected: Bot understands Russian and replies strictly in Ukrainian.",
    ),
    (
        "Group Privacy Check (Untagged Message)",
        "Це тестове повідомлення без тегу бота. Бот не повинен відповідати.",
        "Expected: Bot remains completely silent and only records to SQLite.",
    ),
]


async def run_e2e_tests(selected_index: int = None) -> None:
    """Sends synthetic user messages to the test group to verify live bot behavior."""
    load_dotenv()

    runner_token = os.getenv("TEST_RUNNER_BOT_TOKEN")
    chat_id = os.getenv("TEST_GROUP_CHAT_ID")
    target_bot = os.getenv("TEST_TARGET_BOT_USERNAME", DEFAULT_TARGET_BOT)

    if not runner_token or not chat_id:
        print("Error: TEST_RUNNER_BOT_TOKEN or TEST_GROUP_CHAT_ID not configured in .env")
        sys.exit(1)

    bot = Bot(token=runner_token)
    print(f"Connected as Test Runner Bot.")
    print(f"Target Group Chat ID: {chat_id}")
    print(f"Target Bot Under Test: {target_bot}\n")

    # Determine scenarios to run
    if selected_index is not None:
        if 1 <= selected_index <= len(TEST_SCENARIOS):
            scenarios = [TEST_SCENARIOS[selected_index - 1]]
        else:
            print(f"Invalid index {selected_index}. Choose between 1 and {len(TEST_SCENARIOS)}.")
            return
    else:
        scenarios = TEST_SCENARIOS

    for idx, (name, template, expected) in enumerate(scenarios, start=1):
        message_text = template.format(bot=target_bot)
        print(f"--- [Step {idx}/{len(scenarios)}] {name} ---")
        print(f"Sending: {message_text}")
        print(f"{expected}")

        try:
            await bot.send_message(chat_id=chat_id, text=message_text)
            print("Status: Sent successfully.")
        except Exception as exc:
            print(f"Status: Failed to send: {exc}")

        # Pause between messages so responses in Telegram can be cleanly observed
        if idx < len(scenarios):
            print("Waiting 5 seconds before next scenario...\n")
            await asyncio.sleep(5)

    print("\nE2E testing batch complete. Verify responses directly in the Telegram group.")


def main() -> None:
    """CLI entry point: allows running all tests or a specific test by number."""
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        asyncio.run(run_e2e_tests(selected_index=int(sys.argv[1])))
    else:
        asyncio.run(run_e2e_tests())


if __name__ == "__main__":
    main()
