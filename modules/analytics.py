# Analytics module: delivers owner-only LLM token usage and cost metrics.
# Restricted to the administrator defined in ADMIN_CHAT_ID.
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from typing import Optional
from core.database.telemetry import async_get_token_usage_stats
from core.gcp import GCPTelemetryReport, get_gcp_telemetry
from core.llm import DEFAULT_IMAGE_MODEL, DEFAULT_MODEL
from core.logger import setup_logger

logger = setup_logger("analytics")

NON_OWNER_MESSAGE = "<b>Access Denied:</b> This command is restricted to the bot administrator."

FEATURE_LABELS = {
    "chat": "Chat Dialogs",
    "news": "News Briefings",
    "roast": "Standup Roasts",
    "meme": "Memes / Images (Nano Banana)",
}


def is_owner(update: Update) -> bool:
    """Checks whether the requesting Telegram user is the configured owner.

    The user ID is matched against ADMIN_CHAT_ID loaded from .env.
    """
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if not admin_id or not update.effective_user:
        return False
    return str(update.effective_user.id) == str(admin_id).strip()


def format_stats_report(stats: dict, gcp_report: Optional[GCPTelemetryReport] = None) -> str:
    """Renders strictly official Google Cloud usage and billing telemetry report in English."""
    if not gcp_report or not gcp_report.is_available:
        return (
            "<b>Gemini API Usage Statistics (Google Cloud):</b>\n\n"
            "GCP telemetry service is not configured or credentials are missing.\n"
            "Check <code>GCP_PROJECT_ID</code> and <code>GCP_SERVICE_ACCOUNT_FILE</code> in .env."
        )

    lines = [
        "<b>Gemini API Usage Statistics (Google Cloud)</b>\n",
        "<b>Service:</b> Gemini API (<code>generativelanguage.googleapis.com</code>)\n",
    ]

    # Model tracking: display default models (text & image) and runtime usage
    default_text_model = stats.get("default_model") or DEFAULT_MODEL
    default_image_model = stats.get("default_image_model") or DEFAULT_IMAGE_MODEL
    last_used = stats.get("last_used_model")
    models_used = stats.get("models_used", [])

    lines.append("<b>Models:</b>")
    lines.append(f"  • Default Text: <code>{default_text_model}</code>")
    lines.append(f"  • Default Image: <code>{default_image_model}</code>")
    if last_used:
        lines.append(f"  • Last used: <code>{last_used}</code>")
    lines.append("")

    # 1. Billing / Actual Invoiced Spend
    lines.append("<b>Actual Spend (Google Cloud Billing):</b>")
    if gcp_report.billing:
        if gcp_report.billing.status == "synced":
            lines.append(
                f"  - Month-to-date (MTD): <b>${gcp_report.billing.cost_usd:.4f} {gcp_report.billing.currency}</b>"
            )
        elif gcp_report.billing.status == "pending_first_export":
            lines.append("  - Month-to-date (MTD): <i>Awaiting first BigQuery export (~1-2h)</i>")
        elif gcp_report.billing.status == "unconfigured":
            lines.append("  - Month-to-date (MTD): <i>BigQuery table not configured in .env</i>")
        else:
            lines.append("  - Month-to-date (MTD): <i>Error connecting to BigQuery</i>")
    lines.append("")

    # 2. Live Velocity (Cloud Monitoring)
    if gcp_report.usage:
        lines.append("<b>Current Quota Usage (Cloud Monitoring API):</b>")
        lines.append(
            f"  - Request rate (last 10 min): <b>{gcp_report.usage.current_rate_usage:.2f}</b> req/min"
        )
        lines.append("")

    return "\n".join(lines).strip()


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

    # Retrieve official Google Cloud telemetry (quotas, monitoring, and actual spend)
    gcp_report = await get_gcp_telemetry()

    report_text = format_stats_report(stats, gcp_report)
    MAX_TELEGRAM_LEN = 4000
    if len(report_text) <= MAX_TELEGRAM_LEN:
        await update.effective_message.reply_text(
            report_text,
            parse_mode=ParseMode.HTML,
        )
    else:
        # Deliver long reports in chunks to stay within Telegram's 4096-character limit
        for i in range(0, len(report_text), MAX_TELEGRAM_LEN):
            chunk = report_text[i:i + MAX_TELEGRAM_LEN]
            await update.effective_message.reply_text(
                chunk,
                parse_mode=ParseMode.HTML,
            )


def register_analytics(app: Application) -> None:
    """Registers analytics command handlers in group 0."""
    app.add_handler(CommandHandler("stats", stats_command))


