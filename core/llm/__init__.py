# LLM package providing non-blocking asynchronous access to Google's Gemini models.
# Designed for Raspberry Pi 3B+ to maintain a tiny memory footprint (<5 MB).
from .client import get_gemini_client
from .config import (
    ALLOWED_TELEGRAM_REACTIONS,
    API_ERROR_MESSAGE,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_MODEL,
    DEFAULT_REACTION_MODEL,
    DEFAULT_SYSTEM_INSTRUCTION,
    FLASH_INPUT_COST_PER_MILLION,
    FLASH_OUTPUT_COST_PER_MILLION,
    IMAGE_ERROR_MESSAGE,
    IMAGE_MODEL_ROTATION_CANDIDATES,
    MODEL_ROTATION_CANDIDATES,
    NEWS_SYSTEM_INSTRUCTION,
    REACTION_MODEL_ROTATION_CANDIDATES,
    ROAST_SYSTEM_INSTRUCTION,
    get_candidate_image_models,
    get_candidate_models,
    get_candidate_reaction_models,
)
from .engine import execute_text_generation
from .chat import generate_response
from .meme import _extract_image_data, generate_meme_image
from .news import _search_grounding_available, generate_news_briefing
from .reactions import (
    _build_reaction_prompt,
    _build_reaction_system_instruction,
    decide_message_reaction,
)
from .roast import _build_roast_prompt, generate_roast
from .telemetry import record_usage

__all__ = [
    # Client
    "get_gemini_client",
    # Telemetry and Execution
    "record_usage",
    "execute_text_generation",
    # Text and Conversational
    "generate_response",
    "generate_news_briefing",
    "generate_roast",
    "_build_roast_prompt",
    # Image and Meme
    "generate_meme_image",
    "_extract_image_data",
    # Emoji Reactions
    "decide_message_reaction",
    "_build_reaction_prompt",
    "_build_reaction_system_instruction",
    # Config and Constants
    "ALLOWED_TELEGRAM_REACTIONS",
    "DEFAULT_MODEL",
    "MODEL_ROTATION_CANDIDATES",
    "get_candidate_models",
    "DEFAULT_IMAGE_MODEL",
    "IMAGE_MODEL_ROTATION_CANDIDATES",
    "get_candidate_image_models",
    "DEFAULT_REACTION_MODEL",
    "REACTION_MODEL_ROTATION_CANDIDATES",
    "get_candidate_reaction_models",
    "FLASH_INPUT_COST_PER_MILLION",
    "FLASH_OUTPUT_COST_PER_MILLION",
    "DEFAULT_SYSTEM_INSTRUCTION",
    "API_ERROR_MESSAGE",
    "IMAGE_ERROR_MESSAGE",
    "NEWS_SYSTEM_INSTRUCTION",
    "ROAST_SYSTEM_INSTRUCTION",
    "_search_grounding_available",
]
