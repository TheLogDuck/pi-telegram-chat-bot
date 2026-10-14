# Access control module: enforces Telegram chat/user authorization and admin approval workflows.
import html
import os
import re
from typing import Optional, Set, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from core.database.access import (
    async_get_all_access_grants,
    async_get_or_create_access_request,
    async_is_entity_approved,
    async_set_access_status,
)
from core.logger import setup_logger
from core.telegram_utils import is_bot_mentioned

logger = setup_logger("access_control")

# In-memory cache of approved (entity_type, entity_id) tuples for sub-microsecond lookups
_APPROVED_CACHE: Set[Tuple[str, int]] = set()

# Commands that the administrator can execute in group chats without triggering access denial
ADMIN_BYPASS_COMMANDS: Tuple[str, ...] = (
    "/approve",
    "/reject",
    "/access",
    "/switch_reaction",
)


def get_admin_id() -> Optional[int]:
    """Retrieves numeric ADMIN_CHAT_ID from environment variables."""
    admin_str = os.getenv("ADMIN_CHAT_ID")
    if not admin_str:
        return None
    try:
        return int(admin_str.strip())
    except ValueError:
        logger.warning(f"Invalid non-numeric ADMIN_CHAT_ID: {admin_str}")
        return None


def is_admin(user_id: int) -> bool:
    """Checks whether the specified user matches the administrator ID."""
    admin_id = get_admin_id()
    return admin_id is not None and user_id == admin_id


async def is_authorized(
    entity_type: str,
    entity_id: int,
) -> bool:
    """Verifies if an entity is authorized, checking cache first then SQLite."""
    # Fast-path: Check memory cache first
    if (entity_type, entity_id) in _APPROVED_CACHE:
        return True

    # Database lookup
    approved = await async_is_entity_approved(entity_type, entity_id)
    if approved:
        _APPROVED_CACHE.add((entity_type, entity_id))
    return approved


def is_message_targeting_bot(
    update: Update,
    bot_username: Optional[str],
    bot_id: Optional[int],
) -> bool:
    """Determines whether a message is addressing the bot rather than other users.

    In private chats, all messages inherently target the bot.
    In group chats, the message must be a slash command, mention the bot tag, or reply to the bot.
    """
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return False

    if chat.type == ChatType.PRIVATE:
        return True

    # Check for slash commands (e.g. /roast, /help)
    if message.text and message.text.strip().startswith("/"):
        return True

    # Check for direct mentions (@bot) or replies to bot messages
    return is_bot_mentioned(update, bot_username, bot_id)


async def auth_gatekeeper(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Intercepts incoming updates before command handlers to enforce manual authorization.

    If authorized, execution silently passes through to subsequent handlers.
    If unauthorized, creates a pending request, notifies the admin, and stops propagation.
    """
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    bot_username = context.bot.username if context.bot else None
    bot_id = context.bot.id if context.bot else None

    # In group chats, ignore normal chatter between other group members
    if not is_message_targeting_bot(update, bot_username, bot_id):
        return

    # Option A: Strict scope separation
    if chat.type == ChatType.PRIVATE:
        # In private 1-on-1 chats, bot owner/admin always has full access
        if is_admin(user.id):
            return
        entity_type = "user"
        entity_id = user.id
        entity_title = user.username or user.first_name
    else:
        # In group chats, the group itself must be explicitly authorized
        entity_type = "chat"
        entity_id = chat.id
        entity_title = chat.title or f"Group {chat.id}"

        # Allow admin management commands to pass through without access restriction
        if is_admin(user.id) and message.text and message.text.strip().startswith(ADMIN_BYPASS_COMMANDS):
            return

    # Verify authorization status
    if await is_authorized(entity_type, entity_id):
        return

    # Entity is not authorized: check or register access request
    status, is_new = await async_get_or_create_access_request(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=entity_title,
    )

    admin_id = get_admin_id()

    if is_new and admin_id:
        # Construct approval notification with inline buttons for the admin
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Схвалити",
                    callback_data=f"auth:approve:{entity_type}:{entity_id}",
                ),
                InlineKeyboardButton(
                    "Відхилити",
                    callback_data=f"auth:reject:{entity_type}:{entity_id}",
                ),
            ]
        ])

        if entity_type == "user":
            user_display = html.escape(f"@{user.username}" if user.username else user.first_name)
            admin_msg = (
                f"<b>Запит на доступ до бота:</b>\n"
                f"Користувач: <b>{user_display}</b>\n"
                f"User ID: <code>{user.id}</code>"
            )
        else:
            group_title = html.escape(chat.title or f"Group {chat.id}")
            initiator = html.escape(f"@{user.username}" if user.username else user.first_name)
            admin_msg = (
                f"<b>Запит на доступ для групи:</b>\n"
                f"Група: <b>{group_title}</b>\n"
                f"Chat ID: <code>{chat.id}</code>\n"
                f"Ініціатор: <b>{initiator}</b>"
            )

        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.warning(f"Failed to deliver access notification to admin ({admin_id}): {exc}")

        # Inform user/group that access request was dispatched
        if entity_type == "user":
            notice = (
                "<b>Цей бот є приватним.</b> Доступ надається лише після підтвердження адміністратором.\n"
                "Запит на доступ успішно надіслано адміністратору."
            )
        elif is_admin(user.id):
            notice = (
                "<b>Цей бот є приватним.</b> Доступ для цієї групи ще не активовано.\n"
                "Ви є адміністратором бота: надішліть <code>/approve</code>, щоб активувати доступ для цієї групи."
            )
        else:
            notice = (
                "<b>Цей бот є приватним.</b> Доступ для цієї групи ще не активовано.\n"
                "Запит на підтвердження надіслано адміністратору."
            )
        await message.reply_text(notice, parse_mode=ParseMode.HTML)

    elif status == "pending":
        if entity_type == "chat" and is_admin(user.id):
            pending_msg = (
                "<b>Запит на розгляді:</b> Доступ для цієї групи очікує на активацію.\n"
                "Надішліть <code>/approve</code>, щоб схвалити доступ для цієї групи."
            )
        else:
            pending_msg = "<b>Запит на розгляді:</b> Ваш запит на доступ очікує на підтвердження адміністратором."
        await message.reply_text(
            pending_msg,
            parse_mode=ParseMode.HTML,
        )
    elif status == "rejected":
        await message.reply_text(
            "<b>Доступ обмежено:</b> Доступ до цього бота відхилено адміністратором.",
            parse_mode=ParseMode.HTML,
        )

    # Halt propagation to prevent unauthorized execution of commands or AI handlers
    raise ApplicationHandlerStop


async def auth_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handles inline button clicks from the administrator to approve or reject access."""
    query = update.callback_query
    if not query or not query.data:
        return

    # Verify that the user clicking the button is the authorized bot administrator
    if not is_admin(query.from_user.id):
        await query.answer("You do not have permission to perform this action.", show_alert=True)
        return

    match = re.match(r"^auth:(approve|reject):(user|chat):(-?\d+)$", query.data)
    if not match:
        return

    action, entity_type, entity_id_str = match.groups()
    entity_id = int(entity_id_str)
    new_status = "approved" if action == "approve" else "rejected"

    # Persist the decision to SQLite
    await async_set_access_status(entity_type, entity_id, new_status)

    # Update in-memory cache
    if new_status == "approved":
        _APPROVED_CACHE.add((entity_type, entity_id))
    else:
        _APPROVED_CACHE.discard((entity_type, entity_id))

    action_label = "approved" if action == "approve" else "rejected"
    type_label = "user" if entity_type == "user" else "group"

    # Update the admin notification message to remove inline buttons
    try:
        await query.edit_message_text(
            f"<b>Request {action_label}:</b>\n"
            f"Type: {type_label}\n"
            f"ID: <code>{entity_id}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.warning(f"Failed to edit admin notification message: {exc}")

    # Notify the target user or group about the decision
    if action == "approve":
        try:
            await context.bot.send_message(
                chat_id=entity_id,
                text="<b>Access granted!</b> You can now use the bot.",
                parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.info(f"Could not notify entity {entity_id} of approval: {exc}")

    await query.answer(f"Request {action_label}.")


async def approve_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Allows admin to approve a user ID or chat ID manually via /approve <id>."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not is_admin(user.id):
        return

    if not context.args:
        # If run without arguments inside a group, approve the current group
        if update.effective_chat and update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            chat_id = update.effective_chat.id
            await async_set_access_status("chat", chat_id, "approved")
            _APPROVED_CACHE.add(("chat", chat_id))
            await message.reply_text(
                f"This group (ID: <code>{chat_id}</code>) was successfully approved.",
                parse_mode=ParseMode.HTML,
            )
            return

        await message.reply_text(
            "<b>Usage:</b> <code>/approve &lt;id&gt;</code> or simply <code>/approve</code> inside a group.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await message.reply_text(
            "<b>Error:</b> Please provide a valid numeric ID.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Negative IDs belong to group/supergroup chats in Telegram
    entity_type = "chat" if target_id < 0 else "user"
    await async_set_access_status(entity_type, target_id, "approved")
    _APPROVED_CACHE.add((entity_type, target_id))
    await message.reply_text(
        f"Access for <b>{entity_type}</b> ID <code>{target_id}</code> successfully granted.",
        parse_mode=ParseMode.HTML,
    )


async def reject_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Allows admin to reject or revoke access for a user ID or chat ID via /reject <id>."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not is_admin(user.id):
        return

    # Check if admin replied to a user's message
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        await async_set_access_status("user", target_user.id, "rejected")
        _APPROVED_CACHE.discard(("user", target_user.id))
        target_name = f"@{target_user.username}" if target_user.username else target_user.first_name
        escaped_name = html.escape(target_name)
        await message.reply_text(
            f"Access for <b>{escaped_name}</b> (ID: <code>{target_user.id}</code>) revoked.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not context.args:
        # If run without arguments inside a group, revoke the current group
        if update.effective_chat and update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            chat_id = update.effective_chat.id
            await async_set_access_status("chat", chat_id, "rejected")
            _APPROVED_CACHE.discard(("chat", chat_id))
            await message.reply_text(
                f"Access for this group (ID: <code>{chat_id}</code>) revoked.",
                parse_mode=ParseMode.HTML,
            )
            return

        await message.reply_text(
            "<b>Usage:</b> <code>/reject &lt;id&gt;</code> or reply to a user's message.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await message.reply_text(
            "<b>Error:</b> Please provide a valid numeric ID.",
            parse_mode=ParseMode.HTML,
        )
        return

    entity_type = "chat" if target_id < 0 else "user"
    await async_set_access_status(entity_type, target_id, "rejected")
    _APPROVED_CACHE.discard((entity_type, target_id))
    await message.reply_text(
        f"Access for <b>{entity_type}</b> ID <code>{target_id}</code> revoked.",
        parse_mode=ParseMode.HTML,
    )


async def access_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Displays only approved entities for the admin via /access."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not is_admin(user.id):
        return

    grants = await async_get_all_access_grants()
    # Filter strictly for approved entities to omit rejected or pending entries
    approved_grants = [g for g in grants if g["status"] == "approved"]
    if not approved_grants:
        await message.reply_text(
            "<b>Approved Access List:</b> No approved users or groups found.",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = ["<b>Approved Access List:</b>\n"]
    for g in approved_grants[:20]:  # Limit to 20 most recent
        title = html.escape(g["entity_title"] or "Unknown")
        lines.append(
            f"• [<b>APPROVED</b>] {g['entity_type']} <code>{g['entity_id']}</code> ({title})"
        )

    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


def register_access_control(app: Application) -> None:
    """Registers access control gatekeeper in handler group -1, along with callbacks and admin commands."""
    # Gatekeeper runs in group -1 (after listener) to block unauthorized execution of group 0 handlers
    app.add_handler(
        MessageHandler(filters.ALL, auth_gatekeeper),
        group=-1,
    )
    # Callback query handler for inline button approval
    app.add_handler(
        CallbackQueryHandler(auth_callback_handler, pattern=r"^auth:"),
        group=-1,
    )
    # Admin commands (group 0)
    app.add_handler(CommandHandler("approve", approve_command), group=0)
    app.add_handler(CommandHandler("reject", reject_command), group=0)
    app.add_handler(CommandHandler("access", access_list_command), group=0)


# Backward-compatibility alias
register_auth = register_access_control
