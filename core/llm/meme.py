# Multimodal image and meme generation module using Gemini Nano Banana models.
from typing import Optional
import sys
from google import genai
from google.genai import types
from core.logger import setup_logger
from core.personas import get_persona
from .client import get_gemini_client
from .config import IMAGE_ERROR_MESSAGE, get_candidate_image_models
from .telemetry import record_usage

logger = setup_logger("llm.meme")


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


def _extract_image_data(response: object) -> tuple[Optional[bytes], Optional[str]]:
    """Extracts inline image binary data and mime-type from Gemini candidate parts."""
    candidates = getattr(response, "candidates", None)
    if candidates and candidates[0].content and candidates[0].content.parts:
        for part in candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data, part.inline_data.mime_type
    return None, None


async def generate_meme_image(
    prompt: str,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], Optional[str]]:
    """Generates an image/meme using Google's Nano Banana multimodal models."""
    if not prompt or not prompt.strip():
        return None, None, "Будь ласка, вкажіть опис для зображення.", None

    active_persona = get_persona(persona_key)
    full_prompt = active_persona.meme_prompt_template.format(prompt=prompt.strip())
    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    for model_name in get_candidate_image_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=config,
            )
            data, mime = _extract_image_data(response)
            if data:
                await _dispatch_record_usage(response, model_name, "meme", chat_id, user_id)
                return data, mime, None, model_name
            logger.warning(f"Image model {model_name} returned no image parts.")
        except Exception as exc:
            logger.warning(f"Image generation with {model_name} failed: {exc}. Trying next candidate...")
            continue

    logger.error("All Nano Banana image models exhausted.")
    return None, None, IMAGE_ERROR_MESSAGE, None
