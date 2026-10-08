# Persona management module: allows users to customize the AI's personality.
# Personas persist per user in SQLite, independent of private chats or groups.
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from core.db import async_get_user_persona, async_set_user_persona
from core.logger import setup_logger
from core.personas import PERSONA_REGISTRY, get_persona

logger = setup_logger("persona")

CALLBACK_PREFIX = "persona:set:"


def build_persona_keyboard(current_key: str) -> InlineKeyboardMarkup:
    """Builds an inline keyboard with available personas, marking the active one."""
    keyboard = []
    for key, persona in PERSONA_REGISTRY.items():
        # Text label indicates the active persona without using any emojis
        label = f"[Обрано] {persona.name}" if key == current_key else persona.name
        callback_data = f"{CALLBACK_PREFIX}{key}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


def format_persona_selection_text(persona_key: str) -> str:
    """Formats the explanation text with current persona details."""
    persona = get_persona(persona_key)
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
        # Allow intuitive shortcuts: 'cynic', 'toxic', 'standard', 'default'
        target_key = None
        if requested in ("cynic", "toxic", "цинік", "токсик"):
            target_key = "cynic"
        elif requested in ("standard", "default", "стандартний", "дефолт"):
            target_key = "standard"

        if target_key:
            await async_set_user_persona(user.id, target_key)
            persona = get_persona(target_key)
            await message.reply_text(
                f"<b>Стиль успішно змінено:</b> <b>{persona.name}</b>\n<i>{persona.description}</i>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Default flow: retrieve current persona and display interactive inline buttons
    current_key = await async_get_user_persona(user.id)
    text = format_persona_selection_text(current_key)
    keyboard = build_persona_keyboard(current_key)

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

    # Update message text and refresh buttons to reflect the new selection
    text = format_persona_selection_text(target_key)
    keyboard = build_persona_keyboard(target_key)

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
