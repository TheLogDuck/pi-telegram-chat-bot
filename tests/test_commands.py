# Unit tests for bot commands (/start, /help, /ping, /stats).
# Mocks Telegram Update and Context objects to ensure 100% offline test execution.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
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
from modules.analytics import NON_OWNER_MESSAGE, stats_command


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

    mock_update.effective_message.reply_text.assert_awaited_once_with(
        START_TEXT,
        parse_mode=ParseMode.HTML,
    )

def test_help_command_regular_user() -> None:
    """Verifies that /help sends the public command directory to regular users."""
    mock_update = make_mock_update()
    mock_update.effective_user.id = 11111  # Regular user
    mock_context = MagicMock()

    asyncio.run(help_command(mock_update, mock_context))

    call_text = mock_update.effective_message.reply_text.call_args[0][0]
    assert "Основні команди:" in call_text
    assert "Адміністрування:" not in call_text


def test_help_command_admin(monkeypatch) -> None:
    """Verifies that /help includes administrative tools when called by the owner."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "77777")
    mock_update = make_mock_update()
    mock_update.effective_user.id = 77777  # Admin user
    mock_context = MagicMock()

    asyncio.run(help_command(mock_update, mock_context))

    call_text = mock_update.effective_message.reply_text.call_args[0][0]
    assert "Адміністрування:" in call_text
    assert "/access" in call_text
    assert "/approve" in call_text
    assert "/reject" in call_text
    assert "/switch_reaction" in call_text



def test_ping_command() -> None:
    """Verifies that /ping sends the fast heartbeat pong message."""
    mock_update = make_mock_update()
    mock_context = MagicMock()

    asyncio.run(ping_command(mock_update, mock_context))

    mock_update.effective_message.reply_text.assert_awaited_once_with(
        PING_TEXT,
        parse_mode=ParseMode.HTML,
    )


def test_stats_command_non_owner(monkeypatch) -> None:
    """Verifies that /stats denies access to unauthorized non-owner users."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")
    mock_update = make_mock_update()
    mock_update.effective_user.id = 99999
    mock_context = MagicMock()

    asyncio.run(stats_command(mock_update, mock_context))

    mock_update.effective_message.reply_text.assert_awaited_once_with(
        NON_OWNER_MESSAGE,
        parse_mode=ParseMode.HTML,
    )


def test_stats_command_owner(monkeypatch) -> None:
    """Verifies that /stats returns usage report for the configured owner."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")
    mock_update = make_mock_update()
    mock_update.effective_user.id = 12345
    mock_context = MagicMock()

    with patch("modules.analytics.get_gcp_telemetry", new_callable=AsyncMock) as m_gcp:
        from core.gcp import GCPTelemetryReport

        m_gcp.return_value = GCPTelemetryReport(is_available=False)

        asyncio.run(stats_command(mock_update, mock_context))

        assert mock_update.effective_message.reply_text.await_count == 1
        call_args = mock_update.effective_message.reply_text.await_args
        assert "Статистика використання Gemini API" in call_args[0][0]


def test_set_bot_commands(monkeypatch) -> None:
    """Verifies that set_bot_commands registers default scope and admin scope."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")
    mock_app = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()

    asyncio.run(set_bot_commands(mock_app))

    # Should register public commands and admin-scoped commands
    assert mock_app.bot.set_my_commands.await_count == 2


