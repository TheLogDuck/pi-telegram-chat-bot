# Unit tests for bot commands (/start, /help, /ping, /stats).
# Mocks Telegram Update and Context objects to ensure 100% offline test execution.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update
from telegram.constants import ParseMode
from modules.commands import (
    BOT_COMMANDS,
    BOT_DESCRIPTION,
    BOT_SHORT_DESCRIPTION,
    HELP_TEXT,
    PING_TEXT,
    START_TEXT,
    chat_member_update_handler,
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
    """Verifies that /start sends the expected English greeting text and language keyboard."""
    mock_update = make_mock_update()
    mock_context = MagicMock()

    asyncio.run(start_command(mock_update, mock_context))

    assert mock_update.effective_message.reply_text.await_count == 1
    call_args = mock_update.effective_message.reply_text.await_args
    assert call_args.args[0] == START_TEXT
    assert "/lang" in call_args.args[0]
    assert "reply_markup" in call_args.kwargs
    assert call_args.kwargs["reply_markup"] is not None
    assert call_args.kwargs["parse_mode"] == ParseMode.HTML

def test_help_command_regular_user() -> None:
    """Verifies that /help sends the public command directory to regular users."""
    mock_update = make_mock_update()
    mock_update.effective_user.id = 11111  # Regular user
    mock_context = MagicMock()

    asyncio.run(help_command(mock_update, mock_context))

    call_text = mock_update.effective_message.reply_text.call_args[0][0]
    assert "Core commands:" in call_text
    assert "Administration:" not in call_text


def test_help_command_admin(monkeypatch) -> None:
    """Verifies that /help includes administrative tools when called by the owner."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "77777")
    mock_update = make_mock_update()
    mock_update.effective_user.id = 77777  # Admin user
    mock_context = MagicMock()

    asyncio.run(help_command(mock_update, mock_context))

    call_text = mock_update.effective_message.reply_text.call_args[0][0]
    assert "Administration:" in call_text
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
        assert "Gemini API Usage Statistics" in call_args[0][0]


def test_set_bot_commands(monkeypatch) -> None:
    """Verifies that set_bot_commands registers commands and descriptions."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")
    mock_app = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()
    mock_app.bot.set_my_description = AsyncMock()
    mock_app.bot.set_my_short_description = AsyncMock()

    asyncio.run(set_bot_commands(mock_app))

    # Should register public commands and admin-scoped commands
    assert mock_app.bot.set_my_commands.await_count == 2
    mock_app.bot.set_my_description.assert_awaited_once_with(BOT_DESCRIPTION)
    mock_app.bot.set_my_short_description.assert_awaited_once_with(BOT_SHORT_DESCRIPTION)


def test_commands_localized_language() -> None:
    """Verifies that /start, /help, and /ping output in Russian when chat language is ru."""
    mock_update = make_mock_update()
    mock_update.effective_chat = MagicMock(id=-100888)
    mock_update.effective_user.id = 55555
    mock_context = MagicMock()

    with patch("modules.commands.async_get_chat_language", new_callable=AsyncMock, return_value="ru"):
        # Test /start in Russian
        asyncio.run(start_command(mock_update, mock_context))
        call_text = mock_update.effective_message.reply_text.call_args[0][0]
        assert "Приветствую!" in call_text
        assert "/lang" in call_text

        # Test /ping in Russian
        asyncio.run(ping_command(mock_update, mock_context))
        call_text = mock_update.effective_message.reply_text.call_args[0][0]
        assert "Бот активен и работает на Raspberry Pi." in call_text

        # Test /help in Russian
        asyncio.run(help_command(mock_update, mock_context))
        call_text = mock_update.effective_message.reply_text.call_args[0][0]
        assert "Справка по командам" in call_text


def test_chat_member_welcome_in_groups() -> None:
    """Verifies that adding the bot to a group sends the startup greeting in English."""
    from telegram import Chat, ChatMember, ChatMemberUpdated
    from telegram.constants import ChatMemberStatus, ChatType

    mock_update = MagicMock()
    mock_chat = MagicMock(spec=Chat, id=-100999, type=ChatType.SUPERGROUP)
    mock_update.effective_chat = mock_chat

    old_member = MagicMock(status=ChatMemberStatus.LEFT)
    new_member = MagicMock(status=ChatMemberStatus.MEMBER)
    mock_update.my_chat_member = MagicMock(spec=ChatMemberUpdated, old_chat_member=old_member, new_chat_member=new_member)

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    asyncio.run(chat_member_update_handler(mock_update, mock_context))

    mock_context.bot.send_message.assert_awaited_once()
    call_kwargs = mock_context.bot.send_message.await_args.kwargs
    assert call_kwargs["chat_id"] == -100999
    assert START_TEXT in call_kwargs["text"]
    assert "/lang" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is not None



