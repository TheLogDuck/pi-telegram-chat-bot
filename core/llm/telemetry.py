# Telemetry and token usage tracking for Gemini API requests.
# Calculates estimated USD cost and logs non-blockingly to SQLite.
from typing import Optional
from core.logger import setup_logger
from .config import FLASH_INPUT_COST_PER_MILLION, FLASH_OUTPUT_COST_PER_MILLION

logger = setup_logger("llm.telemetry")


async def record_usage(
    response: object,
    model_name: str,
    feature: str,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """Extracts usage metadata from Gemini response and logs it to SQLite."""
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return

    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = getattr(usage, "total_token_count", prompt_tokens + completion_tokens) or 0

    # Compute estimated cost based on token counts
    cost_usd = (
        (prompt_tokens * FLASH_INPUT_COST_PER_MILLION)
        + (completion_tokens * FLASH_OUTPUT_COST_PER_MILLION)
    ) / 1_000_000.0

    try:
        from core.database.telemetry import async_save_token_usage

        await async_save_token_usage(
            model=model_name,
            feature=feature,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            chat_id=chat_id,
            user_id=user_id,
        )
    except Exception as exc:
        # Prevent telemetry logging errors from blocking AI replies
        logger.warning(f"Failed to record token usage: {exc}")
