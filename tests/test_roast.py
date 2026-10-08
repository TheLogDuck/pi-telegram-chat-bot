# Unit tests for modules/roast.py.
# All tests mock database queries and LLM generation for 100% offline execution.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Chat, Message, Update, User
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import Application
from modules.roast import NO_TARGET_HELP_TEXT, register_roast, roast_command


def make_roast_update(
    text: str,
    reply_user: User = None,
    chat_type: ChatType = ChatType.PRIVATE,
) -> Update:
    """Helper creating a mock Update for roast tests."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.type = chat_type
    chat.id = 12345

    message = MagicMock(spec=Message)
    message.text = text
    message.message_id = 1
    message.chat = chat
    message.reply_text = AsyncMock()

    if reply_user:
        reply_msg = MagicMock(spec=Message)
        reply_msg.from_user = reply_user
        message.reply_to_message = reply_msg
    else:
        message.reply_to_message = None

    update.effective_chat = chat
    update.effective_message = message
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 777
    update.effective_user.username = "sender"
    return update


@patch("modules.roast.async_get_user_messages", new_callable=AsyncMock)
@patch("modules.roast.generate_roast", new_callable=AsyncMock)
def test_roast_command_with_explicit_arg(
    mock_generate: AsyncMock,
    mock_db: AsyncMock,
) -> None:
    """Verifies roast command when target user is provided in context.args."""
    mock_db.return_value = ["люблю каву", "знову дедлайн"]
    mock_generate.return_value = ("**Роаст @developer:** Забагато кави!", "gemini-3.8-flash")

    update = make_roast_update("/roast @developer")
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    context.args = ["@developer"]

    asyncio.run(roast_command(update, context))

    context.bot.send_chat_action.assert_awaited_once_with(
        chat_id=12345,
        action=ChatAction.TYPING,
    )
    mock_db.assert_awaited_once_with(
        chat_id=12345,
        username="@developer",
        user_id=None,
        limit=5,
    )
    mock_generate.assert_awaited_once_with(
        target_name="@developer",
        context_messages=["люблю каву", "знову дедлайн"],
    )
    update.effective_message.reply_text.assert_awaited_once_with(
        "<b>Роаст @developer:</b> Забагато кави!\n\nМодель: gemini-3.8-flash",
        parse_mode=ParseMode.HTML,
    )


@patch("modules.roast.async_get_user_messages", new_callable=AsyncMock)
@patch("modules.roast.generate_roast", new_callable=AsyncMock)
def test_roast_command_from_reply_message(
    mock_generate: AsyncMock,
    mock_db: AsyncMock,
) -> None:
    """Verifies roast command targets author of replied-to message."""
    mock_db.return_value = []
    mock_generate.return_value = ("**Роаст @victim:** Привіт жертві!", "gemini-3.8-flash")

    target_user = MagicMock(spec=User)
    target_user.id = 888
    target_user.username = "victim"

    update = make_roast_update("/roast", reply_user=target_user)
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    context.args = []

    asyncio.run(roast_command(update, context))

    mock_db.assert_awaited_once_with(
        chat_id=12345,
        username="victim",
        user_id=888,
        limit=5,
    )
    mock_generate.assert_awaited_once_with(
        target_name="victim",
        context_messages=[],
    )
    update.effective_message.reply_text.assert_awaited_once_with(
        "<b>Роаст @victim:</b> Привіт жертві!\n\nМодель: gemini-3.8-flash",
        parse_mode=ParseMode.HTML,
    )


def test_roast_command_no_target_shows_help() -> None:
    """Verifies that invoking /roast with no target displays usage help."""
    update = make_roast_update("/roast")
    context = MagicMock()
    context.args = []

    asyncio.run(roast_command(update, context))

    # Should reply with help text in HTML
    update.effective_message.reply_text.assert_awaited_once()
    args, kwargs = update.effective_message.reply_text.call_args
    assert "Кому саме влаштувати прожарку?" in args[0]
    assert kwargs.get("parse_mode") == ParseMode.HTML


def test_register_roast() -> None:
    """Verifies that register_roast registers the CommandHandler."""
    mock_app = MagicMock(spec=Application)
    register_roast(mock_app)
    mock_app.add_handler.assert_called_once()
