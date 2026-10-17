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
START_CALLBACK_PREFIX = "lang:start:"


def build_language_keyboard(
    current_code: str,
    prefix: str = CALLBACK_PREFIX,
) -> InlineKeyboardMarkup:
    """Builds an inline keyboard with available languages, marking the active one."""
    keyboard = []
    badge = get_localized_string("language_selected_badge", current_code)
    for code, name in SUPPORTED_LANGUAGES.items():
        # Text label indicates the active language without using any emojis
        label = f"{badge} {name}" if code == current_code else name
        callback_data = f"{prefix}{code}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


def format_start_text(lang_code: str) -> str:
    """Formats the startup greeting message with language selection invitation."""
    greeting = get_localized_string("start_text", lang_code)
    prompt = get_localized_string("start_language_prompt", lang_code)
    return f"{greeting}\n\n<b>{prompt}</b>"


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
    """Handles the /lang slash command to display the interactive button menu."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    # Retrieve current chat language and display inline button menu
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

    # Determine if callback originated from /start greeting or /lang menu
    is_start_origin = query.data.startswith(START_CALLBACK_PREFIX)
    prefix = START_CALLBACK_PREFIX if is_start_origin else CALLBACK_PREFIX
    target_code = query.data[len(prefix):]

    if not is_supported_language(target_code):
        await query.answer("Невідома мова / Unknown language.")
        return

    # Persist preference for this chat in SQLite
    await async_set_chat_language(chat.id, target_code)
    selected_name = SUPPORTED_LANGUAGES[target_code]
    badge = get_localized_string("language_selected_badge", target_code)

    # Acknowledge callback query to dismiss UI loading state
    await query.answer(f"{badge} {selected_name}")

    # Re-render message in chosen language (greeting for start, directory for lang)
    if is_start_origin:
        text = format_start_text(target_code)
    else:
        text = format_language_selection_text(target_code)
    keyboard = build_language_keyboard(target_code, prefix=prefix)

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
    app.add_handler(CallbackQueryHandler(language_callback_query, pattern=r"^lang:(set|start):"))
