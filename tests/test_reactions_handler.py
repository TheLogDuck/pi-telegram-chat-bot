# Unit tests for modules/reactions.py.
# Fully mocks Telegram Update, Context, and LLM to ensure 100% offline execution.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Chat, Message, ReactionTypeEmoji, Update, User
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest

from modules.reactions import (
    reaction_message_handler,
    register_reactions,
    switch_reaction_command,
)


def make_update(
    chat_id: int = -1001,
    chat_type: ChatType = ChatType.GROUP,
    user_id: int = 12345,
    is_bot: bool = False,
    text: str = "Test message",
    args: list[str] = None,
) -> tuple[MagicMock, MagicMock]:
    """Helper to construct mock Telegram Update and Context objects."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.id = chat_id
    chat.type = chat_type

    user = MagicMock(spec=User)
    user.id = user_id
    user.username = "test_user"
    user.first_name = "Test"
    user.is_bot = is_bot

    message = MagicMock(spec=Message)
    message.text = text
    message.message_id = 999
    message.chat = chat
    message.from_user = user
    message.reply_text = AsyncMock()
    message.set_reaction = AsyncMock()

    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message

    context = MagicMock()
    context.args = args or []
    context.bot.username = "my_bot"
    context.bot.id = 777

    return update, context


@patch("modules.reactions.is_admin", return_value=False)
def test_switch_reaction_denied_for_non_admin(mock_admin: MagicMock) -> None:
    """Verifies that non-admin users cannot toggle reaction settings."""
    update, context = make_update(user_id=99999)

    asyncio.run(switch_reaction_command(update, context))

    update.effective_message.reply_text.assert_not_called()


@patch("modules.reactions.is_admin", return_value=True)
@patch("modules.reactions.async_toggle_reaction_enabled", new_callable=AsyncMock)
def test_switch_reaction_admin_toggles_group(
    mock_toggle: AsyncMock,
    mock_admin: MagicMock,
) -> None:
    """Verifies admin toggling reaction settings in a group chat."""
    mock_toggle.return_value = True  # Enabled
    update, context = make_update(chat_id=-1001, chat_type=ChatType.GROUP)

    asyncio.run(switch_reaction_command(update, context))

    mock_toggle.assert_awaited_once_with(-1001)
    update.effective_message.reply_text.assert_awaited_once()
    reply_args = update.effective_message.reply_text.await_args
    assert "УВІМКНЕНО" in reply_args.args[0]


@patch("modules.reactions.is_admin", return_value=True)
@patch("modules.reactions.async_toggle_reaction_enabled", new_callable=AsyncMock)
def test_switch_reaction_admin_ignores_bot_username_in_group(
    mock_toggle: AsyncMock,
    mock_admin: MagicMock,
) -> None:
    """Verifies that passing @bot_username in a group chat toggles the current group chat."""
    mock_toggle.return_value = True
    update, context = make_update(
        chat_id=-1001,
        chat_type=ChatType.GROUP,
        args=["@SketchyIntelligenceTestBot"],
    )

    asyncio.run(switch_reaction_command(update, context))

    mock_toggle.assert_awaited_once_with(-1001)
    update.effective_message.reply_text.assert_awaited_once()



@patch("modules.reactions.is_admin", return_value=True)
@patch("modules.reactions.async_toggle_reaction_enabled", new_callable=AsyncMock)
def test_switch_reaction_admin_specifies_chat_id_in_pm(
    mock_toggle: AsyncMock,
    mock_admin: MagicMock,
) -> None:
    """Verifies admin toggling a specific chat ID from private messages."""
    mock_toggle.return_value = False  # Disabled
    update, context = make_update(
        chat_id=12345,
        chat_type=ChatType.PRIVATE,
        args=["-100223344"],
    )

    asyncio.run(switch_reaction_command(update, context))

    mock_toggle.assert_awaited_once_with(-100223344)
    update.effective_message.reply_text.assert_awaited_once()
    reply_args = update.effective_message.reply_text.await_args
    assert "ВИМКНЕНО" in reply_args.args[0]


@patch("modules.reactions.async_is_reaction_enabled", new_callable=AsyncMock)
def test_reaction_handler_skips_when_disabled(mock_is_enabled: AsyncMock) -> None:
    """Verifies no reaction processing occurs if reactions are disabled for the chat."""
    mock_is_enabled.return_value = False
    update, context = make_update(chat_id=-1001, text="Just chatting")

    asyncio.run(reaction_message_handler(update, context))

    mock_is_enabled.assert_awaited_once_with(-1001)
    update.effective_message.set_reaction.assert_not_called()


@patch("modules.reactions.async_is_reaction_enabled", new_callable=AsyncMock)
def test_reaction_handler_skips_bot_messages(mock_is_enabled: AsyncMock) -> None:
    """Verifies messages sent by bots are ignored."""
    mock_is_enabled.return_value = True
    update, context = make_update(chat_id=-1001, is_bot=True, text="Beep boop")

    asyncio.run(reaction_message_handler(update, context))

    update.effective_message.set_reaction.assert_not_called()


@patch("modules.reactions.decide_message_reaction", new_callable=AsyncMock)
@patch("modules.reactions.async_get_effective_persona", new_callable=AsyncMock)
@patch("modules.reactions.async_get_recent_chat_messages", new_callable=AsyncMock)
@patch("modules.reactions.async_is_reaction_enabled", new_callable=AsyncMock)
def test_reaction_handler_works_in_private_chat(
    mock_is_enabled: AsyncMock,
    mock_get_recent: AsyncMock,
    mock_get_persona: AsyncMock,
    mock_decide: AsyncMock,
) -> None:
    """Verifies that reactions are evaluated and set on messages in 1-on-1 private chats."""
    mock_is_enabled.return_value = True
    mock_get_recent.return_value = []
    mock_get_persona.return_value = "standard"
    mock_decide.return_value = ("👍", "gemini-2.5-flash-lite")
    update, context = make_update(chat_id=12345, chat_type=ChatType.PRIVATE, text="Private message")

    asyncio.run(reaction_message_handler(update, context))

    update.effective_message.set_reaction.assert_awaited_once()


@patch("modules.reactions.decide_message_reaction", new_callable=AsyncMock)
@patch("modules.reactions.async_get_effective_persona", new_callable=AsyncMock)
@patch("modules.reactions.async_get_recent_chat_messages", new_callable=AsyncMock)
@patch("modules.reactions.async_is_reaction_enabled", new_callable=AsyncMock)
def test_reaction_handler_sets_reaction_when_decided(
    mock_is_enabled: AsyncMock,
    mock_get_recent: AsyncMock,
    mock_get_persona: AsyncMock,
    mock_decide: AsyncMock,
) -> None:

    """Verifies emoji reaction is set on message when LLM decides to react."""
    mock_is_enabled.return_value = True
    mock_get_recent.return_value = [{"username": "alex", "text": "Deploying now"}]
    mock_get_persona.return_value = "standard"
    mock_decide.return_value = ("🔥", "gemini-2.5-flash-lite")

    update, context = make_update(chat_id=-1001, text="Release is live!")

    asyncio.run(reaction_message_handler(update, context))

    mock_decide.assert_awaited_once()
    update.effective_message.set_reaction.assert_awaited_once()
    call_reaction = update.effective_message.set_reaction.await_args.args[0]
    assert len(call_reaction) == 1
    assert isinstance(call_reaction[0], ReactionTypeEmoji)
    assert call_reaction[0].emoji == "🔥"


@patch("modules.reactions.decide_message_reaction", new_callable=AsyncMock)
@patch("modules.reactions.async_get_effective_persona", new_callable=AsyncMock)
@patch("modules.reactions.async_get_recent_chat_messages", new_callable=AsyncMock)
@patch("modules.reactions.async_is_reaction_enabled", new_callable=AsyncMock)
def test_reaction_handler_no_reaction_when_llm_returns_none(
    mock_is_enabled: AsyncMock,
    mock_get_recent: AsyncMock,
    mock_get_persona: AsyncMock,
    mock_decide: AsyncMock,
) -> None:
    """Verifies no reaction is applied when LLM returns None."""
    mock_is_enabled.return_value = True
    mock_get_recent.return_value = []
    mock_get_persona.return_value = "standard"
    mock_decide.return_value = (None, "gemini-2.5-flash-lite")

    update, context = make_update(chat_id=-1001, text="Good morning")

    asyncio.run(reaction_message_handler(update, context))

    update.effective_message.set_reaction.assert_not_called()


@patch("modules.reactions.decide_message_reaction", new_callable=AsyncMock)
@patch("modules.reactions.async_get_effective_persona", new_callable=AsyncMock)
@patch("modules.reactions.async_get_recent_chat_messages", new_callable=AsyncMock)
@patch("modules.reactions.async_is_reaction_enabled", new_callable=AsyncMock)
def test_reaction_handler_handles_telegram_bad_request_gracefully(
    mock_is_enabled: AsyncMock,
    mock_get_recent: AsyncMock,
    mock_get_persona: AsyncMock,
    mock_decide: AsyncMock,
) -> None:
    """Verifies Telegram BadRequest (e.g. reactions disabled in chat) is caught without crashing."""
    mock_is_enabled.return_value = True
    mock_get_recent.return_value = []
    mock_get_persona.return_value = "standard"
    mock_decide.return_value = ("👍", "gemini-2.5-flash-lite")

    update, context = make_update(chat_id=-1001, text="Test message")
    update.effective_message.set_reaction.side_effect = BadRequest("Reactions are disabled")

    # Must complete cleanly without raising exception
    asyncio.run(reaction_message_handler(update, context))
    update.effective_message.set_reaction.assert_awaited_once()

