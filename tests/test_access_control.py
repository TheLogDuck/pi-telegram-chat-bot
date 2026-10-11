# Unit tests for modules/access_control.py access control gatekeeper and admin callbacks.
# All tests mock Telegram network calls for 100% offline execution.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.constants import ChatType, ParseMode
from telegram.ext import ApplicationHandlerStop
from core.database.access import async_set_access_status
from core.database.connection import init_db
from modules.access_control import (
    _APPROVED_CACHE,
    access_list_command,
    approve_command,
    auth_callback_handler,
    auth_gatekeeper,
    is_admin,
    reject_command,
)


@pytest.fixture(autouse=True)
def clear_approved_cache():
    """Ensures in-memory cache is isolated between tests."""
    _APPROVED_CACHE.clear()
    yield
    _APPROVED_CACHE.clear()


def make_update(
    chat_type: ChatType,
    text: str,
    user_id: int = 111,
    chat_id: int = 111,
    username: str = "testuser",
    reply_to_bot: bool = False,
) -> Update:
    """Helper creating mock Updates with necessary user and chat metadata."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.type = chat_type
    chat.id = chat_id
    chat.title = "Test Group" if chat_type != ChatType.PRIVATE else None

    user = MagicMock(spec=User)
    user.id = user_id
    user.username = username
    user.first_name = "Test"

    message = MagicMock(spec=Message)
    message.text = text
    message.message_id = 1
    message.chat = chat
    message.from_user = user
    message.reply_text = AsyncMock()

    if reply_to_bot:
        bot_msg = MagicMock(spec=Message)
        bot_user = MagicMock(spec=User)
        bot_user.id = 999
        bot_msg.from_user = bot_user
        message.reply_to_message = bot_msg
    else:
        message.reply_to_message = None

    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    return update


def make_context(bot_username: str = "my_bot", bot_id: int = 999) -> MagicMock:
    """Helper creating mock context with bot properties and send_message mock."""
    context = MagicMock()
    context.bot.username = bot_username
    context.bot.id = bot_id
    context.bot.send_message = AsyncMock()
    context.args = []
    return context


def test_is_admin(monkeypatch):
    """Verifies is_admin validates against ADMIN_CHAT_ID."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "777")
    assert is_admin(777) is True
    assert is_admin(888) is False

    monkeypatch.delenv("ADMIN_CHAT_ID", raising=False)
    assert is_admin(777) is False


def test_admin_bypasses_gatekeeper(monkeypatch, tmp_path):
    """Verifies that the bot administrator passes through without restriction."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "777")
    update = make_update(ChatType.PRIVATE, "hello", user_id=777)
    context = make_context()

    # Should complete cleanly without raising ApplicationHandlerStop
    asyncio.run(auth_gatekeeper(update, context))
    context.bot.send_message.assert_not_called()
    update.effective_message.reply_text.assert_not_called()


def test_admin_commands_bypass_in_unauthorized_group(monkeypatch):
    """Verifies admin commands in unapproved groups pass without gatekeeper interruption."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "777")
    context = make_context()

    for cmd in ("/approve 123", "/reject 123", "/access", "/switch_reaction"):
        update = make_update(ChatType.GROUP, cmd, user_id=777, chat_id=-9999)
        asyncio.run(auth_gatekeeper(update, context))
        context.bot.send_message.assert_not_called()
        update.effective_message.reply_text.assert_not_called()


def test_private_unauthorized_user_creates_request(monkeypatch, tmp_path):
    """Verifies unauthorized user in DM triggers alert to admin and notice to user."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = make_update(ChatType.PRIVATE, "/start", user_id=123, username="stranger")
    context = make_context()

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(auth_gatekeeper(update, context))

    # Admin received approval notification with inline buttons
    context.bot.send_message.assert_awaited_once()
    admin_args, admin_kwargs = context.bot.send_message.call_args
    assert admin_kwargs["chat_id"] == 9999
    assert "stranger" in admin_kwargs["text"]
    assert "reply_markup" in admin_kwargs

    # User received pending notice
    update.effective_message.reply_text.assert_awaited_once()
    user_msg = update.effective_message.reply_text.call_args[0][0]
    assert "приватним" in user_msg


def test_private_approved_user_passes_through(monkeypatch, tmp_path):
    """Verifies approved user in DM is allowed to execute commands."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    # Manually approve user 123
    asyncio.run(async_set_access_status("user", 123, "approved", db_path=test_db))

    update = make_update(ChatType.PRIVATE, "/roast @someone", user_id=123)
    context = make_context()

    # Passes through without raising ApplicationHandlerStop
    asyncio.run(auth_gatekeeper(update, context))
    context.bot.send_message.assert_not_called()
    update.effective_message.reply_text.assert_not_called()


def test_group_untagged_message_ignored(monkeypatch, tmp_path):
    """Verifies that normal member chatter in groups does not trigger auth requests."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")
    update = make_update(ChatType.GROUP, "just talking to a friend", user_id=123, chat_id=-1001)
    context = make_context()

    # Passes through silently
    asyncio.run(auth_gatekeeper(update, context))
    context.bot.send_message.assert_not_called()
    update.effective_message.reply_text.assert_not_called()


def test_group_tagged_unauthorized_triggers_request(monkeypatch, tmp_path):
    """Verifies bot command in an unapproved group requests approval for the group."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = make_update(ChatType.GROUP, "/roast @someone", user_id=123, chat_id=-1002)
    context = make_context()

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(auth_gatekeeper(update, context))

    # Admin notified of group access request
    context.bot.send_message.assert_awaited_once()
    assert "-1002" in context.bot.send_message.call_args[1]["text"]

    # Group received restricted notice
    update.effective_message.reply_text.assert_awaited_once()


def test_group_approved_passes_through(monkeypatch, tmp_path):
    """Verifies any user in an approved group can use the bot."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    # Approve group chat -1005
    asyncio.run(async_set_access_status("chat", -1005, "approved", db_path=test_db))

    update = make_update(ChatType.GROUP, "@my_bot привіт", user_id=456, chat_id=-1005)
    context = make_context()

    # Allowed without error
    asyncio.run(auth_gatekeeper(update, context))
    context.bot.send_message.assert_not_called()


def test_auth_callback_approve_user(monkeypatch, tmp_path):
    """Verifies admin clicking [Схвалити] persists approval and notifies user."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = MagicMock(spec=Update)
    query = MagicMock(spec=CallbackQuery)
    query.data = "auth:approve:user:555"
    query.from_user = MagicMock(spec=User)
    query.from_user.id = 9999  # Admin
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    context = make_context()

    asyncio.run(auth_callback_handler(update, context))

    # In-memory cache now includes the user
    assert ("user", 555) in _APPROVED_CACHE
    query.edit_message_text.assert_awaited_once()
    context.bot.send_message.assert_awaited_once_with(
        chat_id=555,
        text="<b>Доступ надано!</b> Тепер ви можете повноцінно користуватися ботом.",
        parse_mode=ParseMode.HTML,
    )


def test_auth_callback_non_admin_forbidden(monkeypatch):
    """Verifies that non-admin clicking inline buttons is rejected."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = MagicMock(spec=Update)
    query = MagicMock(spec=CallbackQuery)
    query.data = "auth:approve:user:555"
    query.from_user = MagicMock(spec=User)
    query.from_user.id = 1111  # Not Admin
    query.answer = AsyncMock()
    update.callback_query = query

    context = make_context()
    asyncio.run(auth_callback_handler(update, context))

    query.answer.assert_awaited_once_with(
        "У вас немає прав для виконання цієї дії.", show_alert=True
    )


def test_manual_approve_and_reject_commands(monkeypatch, tmp_path):
    """Verifies admin /approve and /reject commands update status and cache."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = make_update(ChatType.PRIVATE, "/approve 333", user_id=9999)
    context = make_context()
    context.args = ["333"]

    asyncio.run(approve_command(update, context))
    assert ("user", 333) in _APPROVED_CACHE
    update.effective_message.reply_text.assert_awaited_once()

    # Now reject by ID
    context.args = ["333"]
    asyncio.run(reject_command(update, context))
    assert ("user", 333) not in _APPROVED_CACHE

    # Test reject in group without arguments
    group_update = make_update(ChatType.GROUP, "/reject", user_id=9999, chat_id=-1009)
    _APPROVED_CACHE.add(("chat", -1009))
    group_context = make_context()
    asyncio.run(reject_command(group_update, group_context))
    assert ("chat", -1009) not in _APPROVED_CACHE
    group_update.effective_message.reply_text.assert_awaited_once()

    # Test reject in reply to user message
    reply_target = MagicMock(spec=User)
    reply_target.id = 444
    reply_target.username = "baduser"
    reply_update = make_update(ChatType.GROUP, "/reject", user_id=9999)
    reply_update.effective_message.reply_to_message = MagicMock(spec=Message)
    reply_update.effective_message.reply_to_message.from_user = reply_target
    _APPROVED_CACHE.add(("user", 444))
    asyncio.run(reject_command(reply_update, make_context()))
    assert ("user", 444) not in _APPROVED_CACHE


def test_access_list_command(monkeypatch, tmp_path):
    """Verifies /access command displays list of tracked requests."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    asyncio.run(async_set_access_status("user", 888, "approved", db_path=test_db))

    update = make_update(ChatType.PRIVATE, "/access", user_id=9999)
    context = make_context()

    asyncio.run(access_list_command(update, context))
    update.effective_message.reply_text.assert_awaited_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "888" in msg


def test_admin_in_unapproved_group_is_blocked_with_guidance(monkeypatch, tmp_path):
    """Verifies that admin in unapproved group is blocked on regular commands (Option A)."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = make_update(ChatType.GROUP, "/ping", user_id=9999, chat_id=-1099)
    context = make_context()

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(auth_gatekeeper(update, context))

    # Bot sends guidance to the admin in the group
    update.effective_message.reply_text.assert_awaited_once()
    notice = update.effective_message.reply_text.call_args[0][0]
    assert "Ви є адміністратором бота" in notice
    assert "/approve" in notice


def test_admin_management_command_passes_in_unapproved_group(monkeypatch, tmp_path):
    """Verifies that admin can run /approve in an unapproved group to whitelist it."""
    test_db = str(tmp_path / "test.db")
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("ADMIN_CHAT_ID", "9999")

    update = make_update(ChatType.GROUP, "/approve", user_id=9999, chat_id=-1099)
    context = make_context()

    # Passes through cleanly without raising ApplicationHandlerStop
    asyncio.run(auth_gatekeeper(update, context))
    update.effective_message.reply_text.assert_not_called()
