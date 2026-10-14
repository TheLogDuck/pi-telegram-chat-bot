# Unit tests for modules/meme.py.
# Validates prompt parsing, offline image streaming, and fallback handling.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Chat, Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application
from modules.meme import NO_PROMPT_MESSAGE, meme_command, register_meme


def make_meme_update(text: str = "/meme") -> MagicMock:
    """Creates a mock Telegram Update for meme command testing."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.id = 12345

    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = 777

    update.effective_chat = chat
    update.effective_message = message
    return update


def test_meme_command_no_prompt() -> None:
    """Verifies that invoking /meme without args returns usage instructions."""
    update = make_meme_update("/meme")
    context = MagicMock()
    context.args = []

    asyncio.run(meme_command(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(
        NO_PROMPT_MESSAGE,
        parse_mode=ParseMode.HTML,
    )
    update.effective_message.reply_photo.assert_not_called()


@patch("modules.meme.generate_meme_image", new_callable=AsyncMock)
def test_meme_command_success_with_args(mock_generate: AsyncMock) -> None:
    """Verifies that meme_command streams generated photo upon success with model footer."""
    fake_png_bytes = b"\x89PNG\r\n\x1a\nfakeimagecontent"
    mock_generate.return_value = (fake_png_bytes, "image/png", None, "gemini-2.5-flash-image")

    update = make_meme_update("/meme funny cat on pi")
    context = MagicMock()
    context.args = ["funny", "cat", "on", "pi"]
    context.bot.send_chat_action = AsyncMock()

    asyncio.run(meme_command(update, context))

    context.bot.send_chat_action.assert_awaited_once_with(
        chat_id=12345,
        action=ChatAction.UPLOAD_PHOTO,
    )
    mock_generate.assert_awaited_once_with(
        prompt="funny cat on pi",
        chat_id=12345,
        user_id=777,
        persona_key="standard",
    )
    update.effective_message.reply_photo.assert_awaited_once()
    call_kwargs = update.effective_message.reply_photo.await_args.kwargs
    assert call_kwargs["caption"] == "funny cat on pi\n\ngemini-2.5-flash-image"
    assert call_kwargs["parse_mode"] == ParseMode.HTML
    assert call_kwargs["photo"].read() == fake_png_bytes


@patch("modules.meme.generate_meme_image", new_callable=AsyncMock)
def test_meme_command_injected_prompt(mock_generate: AsyncMock) -> None:
    """Verifies that an injected prompt from conversational intent is used."""
    fake_bytes = b"image-data"
    mock_generate.return_value = (fake_bytes, "image/png", None, "gemini-2.5-flash-image")

    update = make_meme_update("@bot мем про програмування")
    context = MagicMock()
    context.args = []
    context.bot.send_chat_action = AsyncMock()

    asyncio.run(meme_command(update, context, prompt="програмування"))

    mock_generate.assert_awaited_once_with(
        prompt="програмування",
        chat_id=12345,
        user_id=777,
        persona_key="standard",
    )
    update.effective_message.reply_photo.assert_awaited_once()
    call_kwargs = update.effective_message.reply_photo.await_args.kwargs
    assert call_kwargs["caption"] == "програмування\n\ngemini-2.5-flash-image"
    assert call_kwargs["parse_mode"] == ParseMode.HTML


@patch("modules.meme.generate_meme_image", new_callable=AsyncMock)
def test_meme_command_failure_fallback(mock_generate: AsyncMock) -> None:
    """Verifies that meme_command sends text error if image generation fails."""
    mock_generate.return_value = (None, None, "Помилка генерації", None)

    update = make_meme_update("/meme bad prompt")
    context = MagicMock()
    context.args = ["bad", "prompt"]
    context.bot.send_chat_action = AsyncMock()

    asyncio.run(meme_command(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(
        "<b>Помилка генерації:</b> Помилка генерації",
        parse_mode=ParseMode.HTML,
    )
    update.effective_message.reply_photo.assert_not_called()


def test_register_meme() -> None:
    """Verifies that register_meme adds the /meme CommandHandler."""
    mock_app = MagicMock(spec=Application)
    register_meme(mock_app)
    mock_app.add_handler.assert_called_once()
