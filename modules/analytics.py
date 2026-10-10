# Analytics module: delivers owner-only LLM token usage and cost metrics.
# Restricted to the administrator defined in ADMIN_CHAT_ID.
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from core.database.telemetry import async_get_token_usage_stats
from core.logger import setup_logger

logger = setup_logger("analytics")

NON_OWNER_MESSAGE = "<b>Помилка доступу:</b> Ця команда доступна виключно адміністратору бота."

FEATURE_LABELS = {
    "chat": "Діалоги (Chat)",
    "news": "Новини (News)",
    "roast": "Прожарки (Roast)",
    "meme": "Меми / Зображення (Nano Banana)",
}


def is_owner(update: Update) -> bool:
    """Checks whether the requesting Telegram user is the configured owner.

    The user ID is matched against ADMIN_CHAT_ID loaded from .env.
    """
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id or not update.effective_user:
        return False
    return str(update.effective_user.id) == str(admin_id).strip()


def format_stats_report(stats: dict) -> str:
    """Renders usage data into a clean, readable text report in Ukrainian."""
    today = stats.get("today", {})
    total = stats.get("total", {})
    by_feature = stats.get("by_feature", {})

    lines = [
        "<b>Статистика використання Gemini API (Tier 1)</b>\n",
        "<b>Тариф:</b> Pay-as-you-go (Tier 1)\n",
        "<b>Сьогодні (UTC):</b>",
        f"  - Запитів: {today.get('calls', 0)}",
        f"  - Токенів: {today.get('total_tokens', 0):,} (Вхід: {today.get('prompt_tokens', 0):,} | Вихід: {today.get('completion_tokens', 0):,})",
        f"  - Орієнтовна вартість: ${today.get('cost_usd', 0.0):.4f}\n",
        "<b>За весь час:</b>",
        f"  - Запитів: {total.get('calls', 0)}",
        f"  - Токенів: {total.get('total_tokens', 0):,}",
        f"  - Орієнтовна вартість: ${total.get('cost_usd', 0.0):.4f}\n",
    ]

    if by_feature:
        lines.append("<b>Використання за функціями:</b>")
        for feat, data in by_feature.items():
            label = FEATURE_LABELS.get(feat, feat)
            lines.append(
                f"  - {label}: {data.get('calls', 0)} запитів | "
                f"{data.get('tokens', 0):,} токенів (${data.get('cost_usd', 0.0):.4f})"
            )
        lines.append("")

    lines.append(
        "<i>Ліміти Tier 1: ~1,000 RPM (текст) | ~500 RPM / 2,000 RPD (Nano Banana).</i>"
    )
    return "\n".join(lines)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /stats command, restricting detailed metrics to the owner."""
    if not update.effective_message:
        return

    # Security check: only the bot owner can view token and billing metrics
    if not is_owner(update):
        await update.effective_message.reply_text(
            NON_OWNER_MESSAGE,
            parse_mode=ParseMode.HTML,
        )
        return

    # Retrieve aggregated token and dollar metrics from local SQLite
    stats = await async_get_token_usage_stats()

    report_text = format_stats_report(stats)
    await update.effective_message.reply_text(
        report_text,
        parse_mode=ParseMode.HTML,
    )


def register_analytics(app: Application) -> None:
    """Registers analytics command handlers in group 0."""
    app.add_handler(CommandHandler("stats", stats_command))


