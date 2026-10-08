# Unit tests for bot commands (/start, /help, /ping, /stats).
# Mocks Telegram Update and Context objects to ensure 100% offline test execution.
import asyncio
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.constants import ParseMode
from modules.commands import (
    BOT_COMMANDS,
    HELP_TEXT,
    PING_TEXT,
    START_TEXT,
    help_command,
    ping_command,
    set_bot_commands,
    start_command,
)
from modules.analytics import stats_command


def make_mock_update() -> MagicMock:
    """Creates a mock Telegram Update object with an async reply_text method."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.effective_message = message
    return update

def test_start_command() -> None:
    """Verifies that /start sends the expected greeting text."""
    mock_update = make_mock_update()
    mock_context = MagicMock()

    asyncio.run(start_command(mock_update, mock_context))

    mock_update.effective_message.reply_text.assert_awaited_once_with(START_TEXT)

def test_help_command() -> None:
    """Verifies that /help sends the command directory."""
    mock_update = make_mock_update()
    mock_context = MagicMock()

    asyncio.run(help_command(mock_update, mock_context))

    mock_update.effective_message.reply_text.assert_awaited_once_with(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
    )

def test_ping_command() -> None:
    """Verifies that /ping sends the fast heartbeat pong message."""
    mock_update = make_mock_update()
    mock_context = MagicMock()

    asyncio.run(ping_command(mock_update, mock_context))

    mock_update.effective_message.reply_text.assert_awaited_once_with(PING_TEXT)

def test_stats_command_non_owner(monkeypatch) -> None:
    """Verifies that /stats denies access to unauthorized non-owner users."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")
    mock_update = make_mock_update()
    mock_update.effective_user.id = 99999
    mock_context = MagicMock()

    asyncio.run(stats_command(mock_update, mock_context))

    mock_update.effective_message.reply_text.assert_awaited_once_with(
        "Ця команда доступна виключно адміністратору бота."
    )


def test_stats_command_owner(monkeypatch) -> None:
    """Verifies that /stats returns usage report for the configured owner."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")
    mock_update = make_mock_update()
    mock_update.effective_user.id = 12345
    mock_context = MagicMock()

    asyncio.run(stats_command(mock_update, mock_context))

    assert mock_update.effective_message.reply_text.await_count == 1
    call_args = mock_update.effective_message.reply_text.await_args
    assert "Статистика використання Gemini API" in call_args[0][0]


def test_set_bot_commands() -> None:
    """Verifies that set_bot_commands sends the BOT_COMMANDS list to Telegram."""
    mock_app = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()

    asyncio.run(set_bot_commands(mock_app))

    mock_app.bot.set_my_commands.assert_awaited_once_with(BOT_COMMANDS)

