# Meme generator module: produces humorous images using Gemini Nano Banana models.
import html
import io
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.database.languages import async_get_chat_language
from core.database.personas import async_get_user_persona
from core.languages import get_localized_string
from core.llm import generate_meme_image
from core.logger import setup_logger

logger = setup_logger("meme")

NO_PROMPT_MESSAGE = (
    "<b>Вкажіть опис:</b> Будь ласка, вкажіть опис для генерації мему. Наприклад:\n"
    "<code>/meme кіт програміст лагодить сервер на Raspberry Pi</code>"
)


async def meme_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    prompt: Optional[str] = None,
) -> None:
    """Handles the /meme command and natural language meme requests."""
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # Extract prompt from direct argument or command args list
    target_prompt = prompt
    if not target_prompt and context.args:
        target_prompt = " ".join(context.args).strip()

    if not target_prompt:
        chat_lang = await async_get_chat_language(chat.id)
        msg = get_localized_string("no_prompt_meme_help", chat_lang)
        await message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    # Inform the user that image synthesis is in progress
    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action=ChatAction.UPLOAD_PHOTO,
        )
    except Exception as exc:
        logger.warning(f"Failed to send upload_photo chat action: {exc}")

    # Extract user ID for telemetry attribution and persona lookup
    user_id = message.from_user.id if message.from_user else None
    persona_key = await async_get_user_persona(user_id) if user_id else "standard"

    # Asynchronously generate the meme image via Nano Banana
    result = await generate_meme_image(
        prompt=target_prompt,
        chat_id=chat.id,
        user_id=user_id,
        persona_key=persona_key,
    )
    if len(result) == 4:
        image_bytes, mime_type, error_msg, model_used = result
    else:
        image_bytes, mime_type, error_msg = result
        model_used = None

    if image_bytes:
        # Stream image from RAM via io.BytesIO without writing to MicroSD storage
        photo_stream = io.BytesIO(image_bytes)
        photo_stream.name = "meme.png"
        escaped_prompt = html.escape(target_prompt)
        caption = (
            f"<b>Мем:</b> {escaped_prompt}\n\n<b>Модель:</b> {html.escape(model_used)}"
            if model_used
            else f"<b>Мем:</b> {escaped_prompt}"
        )
        await message.reply_photo(
            photo=photo_stream,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    else:
        error_text = error_msg or "Не вдалося створити зображення."
        await message.reply_text(
            f"<b>Помилка генерації:</b> {html.escape(error_text)}",
            parse_mode=ParseMode.HTML,
        )


def register_meme(app: Application) -> None:
    """Registers the /meme command handler in group 0."""
    app.add_handler(CommandHandler("meme", meme_command))
