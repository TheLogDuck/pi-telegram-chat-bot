# News briefing generation with Google Search grounding fallback.
import os
from typing import Optional
from google import genai
from google.genai import types
from core.logger import setup_logger
from .config import API_ERROR_MESSAGE, NEWS_SYSTEM_INSTRUCTION, get_candidate_models
from .engine import execute_text_generation

logger = setup_logger("llm.news")

# Track whether Google Search tool quota is available on this API key.
# On Free Tier accounts, this disables cleanly on the first 429 to avoid retry storms.
_search_grounding_available = os.getenv("ENABLE_SEARCH_GROUNDING", "true").lower() in ("true", "1", "yes")


async def generate_news_briefing(
    topic: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a news briefing grounded with Google Search."""
    if topic and topic.strip():
        prompt = (
            f"Підготуй стислий інформаційний дайджест останніх актуальних новин "
            f"на тему: {topic.strip()}."
        )
    else:
        prompt = (
            "Підготуй стислий інформаційний дайджест головних світових "
            "та технологічних новин на сьогодні."
        )

    global _search_grounding_available

    # Attempt Grounded Search with Google Search tool if available
    if _search_grounding_available:
        grounded_config = types.GenerateContentConfig(
            system_instruction=NEWS_SYSTEM_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        text, model = await execute_text_generation(
            prompt=prompt,
            config=grounded_config,
            candidates=get_candidate_models(),
            feature="news",
            client=client,
            chat_id=chat_id,
            user_id=user_id,
        )
        if text:
            return text, model
        # Disable tool grounding on quota failure (e.g. Free Tier 429) and fall back
        _search_grounding_available = False
        logger.info("Search tool quota unavailable. Falling back to standard AI synthesis.")

    # Fallback to standard model synthesis (fast, zero external search tool dependency)
    standard_config = types.GenerateContentConfig(
        system_instruction=NEWS_SYSTEM_INSTRUCTION,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    text, model = await execute_text_generation(
        prompt=prompt,
        config=standard_config,
        candidates=get_candidate_models(),
        feature="news",
        client=client,
        chat_id=chat_id,
        user_id=user_id,
    )
    return (text, model) if text else (API_ERROR_MESSAGE, None)
