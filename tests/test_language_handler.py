# Unit tests for the /lang slash command and inline button interaction.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram.constants import ParseMode
from modules.language import (
    CALLBACK_PREFIX,
    START_CALLBACK_PREFIX,
    build_language_keyboard,
    format_language_selection_text,
    format_start_text,
    language_callback_query,
    language_command,
)


def test_build_language_keyboard_marks_active_language() -> None:
    """Verifies that the inline keyboard marks the selected language."""
    markup_en = build_language_keyboard("en", prefix=START_CALLBACK_PREFIX)
    buttons_en = [row[0] for row in markup_en.inline_keyboard]
    assert len(buttons_en) == 4

    labels_en = {b.callback_data: b.text for b in buttons_en}
    assert "[Selected] English" in labels_en[f"{START_CALLBACK_PREFIX}en"]
    assert "Українська" in labels_en[f"{START_CALLBACK_PREFIX}uk"]

    markup_uk = build_language_keyboard("uk", prefix=CALLBACK_PREFIX)
    buttons_uk = [row[0] for row in markup_uk.inline_keyboard]
    labels_uk = {b.callback_data: b.text for b in buttons_uk}
    assert "[Обрано] Українська" in labels_uk[f"{CALLBACK_PREFIX}uk"]


def test_format_language_selection_text() -> None:
    """Verifies localized description text formatting."""
    text_uk = format_language_selection_text("uk")
    text_ru = format_language_selection_text("ru")

    assert "Оберіть мову" in text_uk
    assert "Українська" in text_uk

    assert "Выберите язык" in text_ru
    assert "Русский" in text_ru


def test_language_command_ignores_arguments_and_shows_menu() -> None:
    """Verifies that passing arguments like '/lang ru' still shows the interactive menu."""
    mock_update = MagicMock()
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message
    mock_update.effective_chat = MagicMock(id=-100123)

    mock_context = MagicMock()
    mock_context.args = ["ru"]

    with patch("modules.language.async_get_chat_language", new_callable=AsyncMock, return_value="uk") as mock_get, \
         patch("modules.language.async_set_chat_language", new_callable=AsyncMock) as mock_set:
        asyncio.run(language_command(mock_update, mock_context))

        mock_set.assert_not_called()
        mock_get.assert_awaited_once_with(-100123)
        mock_message.reply_text.assert_awaited_once()
        kwargs = mock_message.reply_text.call_args.kwargs
        assert kwargs["reply_markup"] is not None
        assert kwargs["parse_mode"] == ParseMode.HTML


def test_language_command_without_arguments_shows_menu() -> None:
    """Verifies that /lang with no arguments sends an interactive keyboard."""
    mock_update = MagicMock()
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message
    mock_update.effective_chat = MagicMock(id=-100123)

    mock_context = MagicMock()
    mock_context.args = []

    with patch("modules.language.async_get_chat_language", new_callable=AsyncMock, return_value="uk"):
        asyncio.run(language_command(mock_update, mock_context))

        mock_message.reply_text.assert_awaited_once()
        kwargs = mock_message.reply_text.call_args.kwargs
        assert kwargs["reply_markup"] is not None
        assert kwargs["parse_mode"] == ParseMode.HTML


def test_language_callback_query_updates_chat_language() -> None:
    """Verifies clicking an inline button updates SQLite and edits the message."""
    mock_update = MagicMock()
    mock_query = AsyncMock()
    mock_query.data = f"{CALLBACK_PREFIX}de"
    mock_update.callback_query = mock_query
    mock_update.effective_chat = MagicMock(id=-100999)

    mock_context = MagicMock()

    with patch("modules.language.async_set_chat_language", new_callable=AsyncMock) as mock_set:
        asyncio.run(language_callback_query(mock_update, mock_context))

        mock_set.assert_awaited_once_with(-100999, "de")
        mock_query.answer.assert_awaited_once()
        mock_query.edit_message_text.assert_awaited_once()


def test_start_callback_query_updates_greeting_in_language() -> None:
    """Verifies clicking a language button on the start message translates greeting to target language."""
    mock_update = MagicMock()
    mock_query = AsyncMock()
    mock_query.data = f"{START_CALLBACK_PREFIX}uk"
    mock_update.callback_query = mock_query
    mock_update.effective_chat = MagicMock(id=-100888)

    mock_context = MagicMock()

    with patch("modules.language.async_set_chat_language", new_callable=AsyncMock) as mock_set:
        asyncio.run(language_callback_query(mock_update, mock_context))

        mock_set.assert_awaited_once_with(-100888, "uk")
        mock_query.answer.assert_awaited_once()
        mock_query.edit_message_text.assert_awaited_once()
        call_kwargs = mock_query.edit_message_text.call_args.kwargs
        assert "Вітаю!" in call_kwargs["text"]
