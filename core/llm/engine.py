# Text generation engine managing automatic candidate rotation and failover.
from typing import Optional
import sys
from google import genai
from google.genai import types
from core.logger import setup_logger
from .client import get_gemini_client
from .concurrency import get_llm_semaphore
from .telemetry import record_usage

logger = setup_logger("llm.engine")


async def _dispatch_record_usage(
    response: object,
    model_name: str,
    feature: str,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """Dispatches token recording, respecting any active patches on core.llm.record_usage."""
    llm_mod = sys.modules.get("core.llm")
    recorder = getattr(llm_mod, "record_usage", record_usage) if llm_mod else record_usage
    await recorder(response, model_name, feature, chat_id, user_id)


async def execute_text_generation(
    prompt: str,
    config: types.GenerateContentConfig,
    candidates: list[str],
    feature: str,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Tries candidate models in order for text generation, recording token usage on success.

    Centralizes the model rotation loop, API exception handling, and SQLite
    usage telemetry in one place to keep individual feature functions lean.
    Uses an asyncio.Semaphore to bound concurrent API calls and safeguard Pi RAM/CPU.
    """
    llm_client = client or get_gemini_client()
    semaphore = get_llm_semaphore()
    async with semaphore:
        for model_name in candidates:
            try:
                response = await llm_client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if response and getattr(response, "text", None):
                    text = response.text.strip()
                    if text:
                        await _dispatch_record_usage(response, model_name, feature, chat_id, user_id)
                        return text, model_name
                logger.warning(f"Model {model_name} returned empty text for {feature}.")
            except Exception as exc:
                logger.warning(f"Model {model_name} failed for {feature}: {exc}. Rotating...")
                continue

    logger.error(f"All candidate models exhausted for feature: {feature}.")
    return None, None
