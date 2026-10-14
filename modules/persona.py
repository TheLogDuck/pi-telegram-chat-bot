# Persona management module: allows users to customize the AI's personality.
# Personas persist per user in SQLite, independent of private chats or groups.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from core.database.languages import async_get_chat_language
from core.database.personas import async_get_user_persona, async_set_user_persona
from core.logger import setup_logger
from core.personas import PERSONA_REGISTRY, get_persona

logger = setup_logger("persona")

CALLBACK_PREFIX = "persona:set:"


def build_persona_keyboard(current_key: str, lang_code: str = "uk") -> InlineKeyboardMarkup:
    """Builds an inline keyboard with available personas, marking the active one."""
    tag = "[Обрано]"
    if lang_code == "ru":
        tag = "[Выбрано]"
    elif lang_code == "en":
        tag = "[Selected]"
    elif lang_code == "de":
        tag = "[Ausgewählt]"

    keyboard = []
    for key, persona in PERSONA_REGISTRY.items():
        # Text label indicates the active persona without using any emojis
        label = f"{tag} {persona.name}" if key == current_key else persona.name
        callback_data = f"{CALLBACK_PREFIX}{key}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


def format_persona_selection_text(persona_key: str, lang_code: str = "uk") -> str:
    """Formats the explanation text with current persona details in the chat's language."""
    persona = get_persona(persona_key)
    if lang_code == "ru":
        return (
            "<b>Выбор стиля общения бота:</b>\n\n"
            f"Текущая персона: <b>{persona.name}</b>\n"
            f"<i>{persona.description}</i>\n\n"
            "Этот стиль применяется для ваших диалогов, прожарок (/roast) и генерации мемов (/meme) "
            "как в личных сообщениях, так и в групповых чатах.\n\n"
            "Нажмите кнопку ниже, чтобы изменить персону:"
        )
    elif lang_code == "en":
        return (
            "<b>Bot communication style selection:</b>\n\n"
            f"Current persona: <b>{persona.name}</b>\n"
            f"<i>{persona.description}</i>\n\n"
            "This style applies to all dialogues, roasts (/roast), and meme generation (/meme) "
            "both in private messages and group chats.\n\n"
            "Click a button below to change persona:"
        )
    elif lang_code == "de":
        return (
            "<b>Auswahl des Kommunikationsstils des Bots:</b>\n\n"
            f"Aktuelle Persona: <b>{persona.name}</b>\n"
            f"<i>{persona.description}</i>\n\n"
            "Dieser Stil gilt für Ihre Dialoge, Roasts (/roast) und Meme-Generierung (/meme) "
            "sowohl in privaten Nachrichten als auch in Gruppen-Chats.\n\n"
            "Klicken Sie unten, um die Persona zu ändern:"
        )
    return (
        "<b>Вибір стилю спілкування бота:</b>\n\n"
        f"Поточна персона: <b>{persona.name}</b>\n"
        f"<i>{persona.description}</i>\n\n"
        "Цей стиль застосовується для ваших діалогів, прожарок (/roast) та генерації мемів (/meme) "
        "як в особистих повідомленнях, так і в групових чатах.\n\n"
        "Натисніть кнопку нижче, щоб змінити персону:"
    )


async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /persona slash command to view or switch personas."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    # Check if a specific persona key was provided directly as an argument
    if context.args:
        requested = context.args[0].strip().lower()
        # Allow intuitive shortcuts: 'standard', 'default', 'meme_lord'
        target_key = None
        if requested in ("standard", "default", "стандартний", "дефолт"):
            target_key = "standard"
        elif requested in ("meme_lord", "memelord", "meme", "мемлорд", "мем_лорд", "мем"):
            target_key = "meme_lord"

        if target_key:
            await async_set_user_persona(user.id, target_key)
            persona = get_persona(target_key)
            await message.reply_text(
                f"<b>Стиль успішно змінено:</b> <b>{persona.name}</b>\n<i>{persona.description}</i>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Default flow: retrieve current persona and display interactive inline buttons in chat's language
    current_key = await async_get_user_persona(user.id)
    chat = update.effective_chat
    lang_code = await async_get_chat_language(chat.id) if chat else "uk"
    text = format_persona_selection_text(current_key, lang_code=lang_code)
    keyboard = build_persona_keyboard(current_key, lang_code=lang_code)

    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


async def persona_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes button clicks from the inline persona selection keyboard."""
    query = update.callback_query
    if not query or not query.data:
        return

    user = update.effective_user
    if not user:
        await query.answer()
        return

    # Extract target persona key from callback payload
    target_key = query.data[len(CALLBACK_PREFIX):]
    if target_key not in PERSONA_REGISTRY:
        await query.answer("Невідома персона.")
        return

    # Save preference for the clicking user in SQLite
    await async_set_user_persona(user.id, target_key)
    selected_persona = get_persona(target_key)

    # Acknowledge the callback query to dismiss loading animation in Telegram UI
    await query.answer(f"Обрано: {selected_persona.name}")

    # Update message text and refresh buttons to reflect the new selection in chat's language
    chat = update.effective_chat
    lang_code = await async_get_chat_language(chat.id) if chat else "uk"
    text = format_persona_selection_text(target_key, lang_code=lang_code)
    keyboard = build_persona_keyboard(target_key, lang_code=lang_code)

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        # Ignore telegram error if content hasn't changed (e.g. repeated click)
        logger.debug(f"Failed to edit persona message: {exc}")


def register_persona(app: Application) -> None:
    """Registers persona handlers in group 0."""
    app.add_handler(CommandHandler("persona", persona_command))
    app.add_handler(CallbackQueryHandler(persona_callback_query, pattern=f"^{CALLBACK_PREFIX}"))
