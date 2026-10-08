# Unit tests for modules/conversational.py.
# Validates tag-only group enforcement, mention stripping, and offline LLM calls.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Chat, Message, Update, User
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import Application
from modules.conversational import (
    EMPTY_TAG_PROMPT,
    clean_bot_mention,
    conversational_chat_handler,
    is_bot_mentioned,
    register_conversational,
)


def make_chat_update(
    chat_type: ChatType,
    text: str,
    reply_from_user_id: int = None,
) -> MagicMock:
    """Creates a mock Update with specified chat type, text, and reply structure."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.type = chat_type
    chat.id = 123456

    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()

    if reply_from_user_id is not None:
        reply_user = MagicMock(spec=User)
        reply_user.id = reply_from_user_id
        reply_msg = MagicMock(spec=Message)
        reply_msg.from_user = reply_user
        message.reply_to_message = reply_msg
    else:
        message.reply_to_message = None

    update.effective_chat = chat
    update.effective_message = message
    return update


def test_is_bot_mentioned_private_chat() -> None:
    """Verifies that private direct messages are always considered addressed to the bot."""
    update = make_chat_update(ChatType.PRIVATE, "Привіт!")
    assert is_bot_mentioned(update, "my_bot", 999) is True


def test_is_bot_mentioned_group_untagged() -> None:
    """Verifies that untagged group messages are ignored."""
    update = make_chat_update(ChatType.GROUP, "Хтось знає відповідь?")
    assert is_bot_mentioned(update, "my_bot", 999) is False


def test_is_bot_mentioned_group_tagged_single_at() -> None:
    """Verifies tag recognition with standard @mention."""
    update = make_chat_update(ChatType.GROUP, "@my_bot розкажи жарт")
    assert is_bot_mentioned(update, "my_bot", 999) is True


def test_is_bot_mentioned_group_tagged_double_at() -> None:
    """Verifies tag recognition with double @@mention typo."""
    update = make_chat_update(ChatType.GROUP, "@@my_bot привіт")
    assert is_bot_mentioned(update, "my_bot", 999) is True


def test_is_bot_mentioned_group_reply_to_bot() -> None:
    """Verifies recognition when replying to a message previously sent by the bot."""
    bot_id = 999
    update = make_chat_update(ChatType.GROUP, "Дякую!", reply_from_user_id=bot_id)
    assert is_bot_mentioned(update, "my_bot", bot_id) is True


def test_clean_bot_mention() -> None:
    """Verifies that @bot and @@bot are cleanly stripped from prompt strings."""
    assert clean_bot_mention("@my_bot розкажи анекдот", "my_bot") == "розкажи анекдот"
    assert clean_bot_mention("@@my_bot що таке AI?", "my_bot") == "що таке AI?"
    assert clean_bot_mention("@my_bot", "my_bot") == ""
    assert clean_bot_mention("привіт @my_bot як ти?", "my_bot") == "привіт  як ти?"


def test_conversational_handler_ignores_untagged_group() -> None:
    """Verifies that the handler stays silent when a group message is not tagged."""
    update = make_chat_update(ChatType.GROUP, "Звичайне повідомлення")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_not_called()
    context.bot.send_chat_action.assert_not_called()


def test_conversational_handler_empty_tag_greeting() -> None:
    """Verifies that tagging the bot with no query returns the greeting prompt."""
    update = make_chat_update(ChatType.GROUP, "@my_bot")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(EMPTY_TAG_PROMPT)


@patch("modules.conversational.generate_response", new_callable=AsyncMock)
def test_conversational_handler_tagged_generates_ai_response(mock_generate: AsyncMock) -> None:
    """Verifies typing action and Gemini generation when tagged with a question."""
    mock_generate.return_value = "Це чудове запитання про науку."
    update = make_chat_update(ChatType.GROUP, "@my_bot розкажи про зорі")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999
    context.bot.send_chat_action = AsyncMock()

    asyncio.run(conversational_chat_handler(update, context))

    context.bot.send_chat_action.assert_awaited_once_with(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )
    mock_generate.assert_awaited_once_with("розкажи про зорі")
    update.effective_message.reply_text.assert_awaited_once_with(
        "Це чудове запитання про науку.",
        parse_mode=ParseMode.HTML,
    )


def test_conversational_handler_dispatches_ping_intent() -> None:
    """Verifies that tagging the bot with 'пінг' or 'пинг' routes to ping_command."""
    from modules.commands import PING_TEXT

    update = make_chat_update(ChatType.GROUP, "@my_bot пінг")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(PING_TEXT)


def test_conversational_handler_dispatches_help_intent() -> None:
    """Verifies that tagging the bot with 'допомога' routes to help_command."""
    from modules.commands import HELP_TEXT

    update = make_chat_update(ChatType.GROUP, "@my_bot допомога")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(HELP_TEXT)


@patch("modules.conversational.news_command", new_callable=AsyncMock)
def test_conversational_handler_dispatches_news_intent(mock_news: AsyncMock) -> None:
    """Verifies that tagging the bot with 'новини про космос' routes to news_command with topic."""
    update = make_chat_update(ChatType.GROUP, "@my_bot новини про космос")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    mock_news.assert_awaited_once_with(update, context, topic="космос")


def test_register_conversational() -> None:
    """Verifies that register_conversational adds a message handler in group 0."""
    mock_app = MagicMock(spec=Application)
    register_conversational(mock_app)
    mock_app.add_handler.assert_called_once()
    assert mock_app.add_handler.call_args[1]["group"] == 0
