# Unit tests for modules/news.py.
# Validates /news command parsing, typing indicator, and mocked LLM generation.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Chat, Message, Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import Application
from modules.news import news_command, register_news


def make_news_update(text: str = "/news") -> MagicMock:
    """Creates a mock Update for the news command."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.type = ChatType.PRIVATE
    chat.id = 12345

    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()

    update.effective_chat = chat
    update.effective_message = message
    update.effective_user = None
    return update


@patch("modules.news.generate_news_briefing", new_callable=AsyncMock)
def test_news_command_with_explicit_topic(mock_generate: AsyncMock) -> None:
    """Verifies that news_command passes the explicit topic to generate_news_briefing."""
    mock_generate.return_value = ("1. Новини штучного інтелекту...", "gemini-3.8-flash")
    update = make_news_update("/news AI")
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    context.args = ["AI"]

    asyncio.run(news_command(update, context, topic="штучний інтелект"))

    context.bot.send_chat_action.assert_awaited_once_with(
        chat_id=12345,
        action=ChatAction.TYPING,
    )
    mock_generate.assert_awaited_once_with(
        topic="штучний інтелект",
        chat_id=12345,
        user_id=None,
        language="uk",
    )
    update.effective_message.reply_text.assert_awaited_once_with(
        "1. Новини штучного інтелекту...\n\nМодель: gemini-3.8-flash",
        parse_mode=ParseMode.HTML,
    )


@patch("modules.news.generate_news_briefing", new_callable=AsyncMock)
def test_news_command_with_context_args(mock_generate: AsyncMock) -> None:
    """Verifies topic extraction from context.args when topic argument is None."""
    mock_generate.return_value = ("1. Новини космосу...", "gemini-3.8-flash")
    update = make_news_update("/news space tech")
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    context.args = ["space", "tech"]

    asyncio.run(news_command(update, context))

    mock_generate.assert_awaited_once_with(
        topic="space tech",
        chat_id=12345,
        user_id=None,
        language="uk",
    )
    update.effective_message.reply_text.assert_awaited_once_with(
        "1. Новини космосу...\n\nМодель: gemini-3.8-flash",
        parse_mode=ParseMode.HTML,
    )


@patch("modules.news.generate_news_briefing", new_callable=AsyncMock)
def test_news_command_default_headlines(mock_generate: AsyncMock) -> None:
    """Verifies that news_command without arguments generates default headlines."""
    mock_generate.return_value = ("1. Головні новини...", "gemini-3.8-flash")
    update = make_news_update("/news")
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    context.args = []

    asyncio.run(news_command(update, context))

    mock_generate.assert_awaited_once_with(
        topic=None,
        chat_id=12345,
        user_id=None,
        language="uk",
    )
    update.effective_message.reply_text.assert_awaited_once_with(
        "1. Головні новини...\n\nМодель: gemini-3.8-flash",
        parse_mode=ParseMode.HTML,
    )


def test_register_news() -> None:
    """Verifies that register_news adds the CommandHandler for 'news'."""
    mock_app = MagicMock(spec=Application)
    register_news(mock_app)
    mock_app.add_handler.assert_called_once()
