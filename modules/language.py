# Chat language management module: allows switching the bot's communication language.
# Settings persist per chat/group in SQLite and are accessible by any user.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from core.database.languages import async_get_chat_language, async_set_chat_language
from core.languages import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_localized_string,
    is_supported_language,
)
from core.logger import setup_logger

logger = setup_logger("language")

CALLBACK_PREFIX = "lang:set:"


def build_language_keyboard(current_code: str) -> InlineKeyboardMarkup:
    """Builds an inline keyboard with available languages, marking the active one."""
    keyboard = []
    for code, name in SUPPORTED_LANGUAGES.items():
        # Text label indicates the active language without using any emojis
        label = f"[Обрано] {name}" if code == current_code else name
        callback_data = f"{CALLBACK_PREFIX}{code}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


def format_language_selection_text(lang_code: str) -> str:
    """Formats the explanation text with current language details."""
    lang_name = SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])
    title = get_localized_string("select_language_title", lang_code)
    label = get_localized_string("current_language_label", lang_code)
    help_text = get_localized_string("language_selection_help", lang_code)

    return (
        f"{title}\n\n"
        f"{label}: <b>{lang_name}</b>\n"
        f"<i>{help_text}</i>\n\n"
        "Натисніть кнопку нижче, щоб обрати мову / Click a button below to choose language:"
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /lang slash command to view or switch the chat's language."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    # Check if a specific language code was passed directly as an argument (e.g., /lang ru)
    if context.args:
        requested = context.args[0].strip().lower()
        # Map common aliases
        alias_map = {
            "ua": "uk",
            "ukr": "uk",
            "ukrainian": "uk",
            "українська": "uk",
            "ru": "ru",
            "rus": "ru",
            "russian": "ru",
            "русский": "ru",
            "en": "en",
            "eng": "en",
            "english": "en",
            "англійська": "en",
            "английский": "en",
            "de": "de",
            "ger": "de",
            "deutsch": "de",
            "german": "de",
            "німецька": "de",
            "немецкий": "de",
        }
        target_code = alias_map.get(requested, requested)

        if is_supported_language(target_code):
            await async_set_chat_language(chat.id, target_code)
            lang_name = SUPPORTED_LANGUAGES[target_code]
            success_msg = get_localized_string("language_switched_success", target_code)
            await message.reply_text(
                f"<b>{success_msg} {lang_name}.</b>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Default interactive flow: retrieve current chat language and display inline buttons
    current_code = await async_get_chat_language(chat.id)
    text = format_language_selection_text(current_code)
    keyboard = build_language_keyboard(current_code)

    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


async def language_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes button clicks from the inline language selection keyboard."""
    query = update.callback_query
    chat = update.effective_chat
    if not query or not query.data or not chat:
        return

    # Extract target language code from callback payload
    target_code = query.data[len(CALLBACK_PREFIX):]
    if not is_supported_language(target_code):
        await query.answer("Невідома мова / Unknown language.")
        return

    # Persist preference for this chat in SQLite
    await async_set_chat_language(chat.id, target_code)
    selected_name = SUPPORTED_LANGUAGES[target_code]

    # Acknowledge callback query to dismiss UI loading state
    await query.answer(f"Обрано: {selected_name}")

    # Update message text and refresh buttons to reflect the new selection
    text = format_language_selection_text(target_code)
    keyboard = build_language_keyboard(target_code)

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        # Ignore telegram error if content hasn't changed (e.g. repeated click)
        logger.debug(f"Failed to edit language message: {exc}")


def register_language(app: Application) -> None:
    """Registers /lang command and callback handlers in group 0."""
    app.add_handler(CommandHandler("lang", language_command))
    app.add_handler(CallbackQueryHandler(language_callback_query, pattern=f"^{CALLBACK_PREFIX}"))
