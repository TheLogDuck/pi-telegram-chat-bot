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


def _inject_language_directive(instruction: str, language: Optional[str]) -> str:
    """Injects the requested output language directive into news instructions."""
    if not language or language == "uk":
        return instruction

    from core.languages import get_language_directive

    directive = get_language_directive(language)
    ua_phrase = "виключно українською мовою."
    if ua_phrase in instruction:
        return instruction.replace(ua_phrase, directive)
    return f"{instruction}\n\n{directive}"


def _build_news_prompt(topic: Optional[str], language: Optional[str]) -> str:
    """Builds localized search grounding prompt for news briefings."""
    clean_topic = topic.strip() if topic else None
    lang = language or "uk"

    if lang == "ru":
        if clean_topic:
            return f"Подготовь краткий информационный дайджест последних актуальных новостей на тему: {clean_topic}."
        return "Подготовь краткий информационный дайджест главных мировых и технологических новостей на сегодня."
    elif lang == "en":
        if clean_topic:
            return f"Prepare a concise news digest of the latest news on topic: {clean_topic}."
        return "Prepare a concise digest of top world and tech news for today."
    elif lang == "de":
        if clean_topic:
            return f"Erstelle eine prägnante Übersicht der aktuellen Nachrichten zum Thema: {clean_topic}."
        return "Erstelle eine prägnante Übersicht der wichtigsten Welt- und Technologienachrichten für heute."
    else:
        # Default Ukrainian
        if clean_topic:
            return f"Підготуй стислий інформаційний дайджест останніх актуальних новин на тему: {clean_topic}."
        return "Підготуй стислий інформаційний дайджест головних світових та технологічних новин на сьогодні."


async def generate_news_briefing(
    topic: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    language: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a news briefing grounded with Google Search in the requested language."""
    prompt = _build_news_prompt(topic, language)
    effective_instruction = _inject_language_directive(NEWS_SYSTEM_INSTRUCTION, language)

    global _search_grounding_available

    # Attempt Grounded Search with Google Search tool if available
    if _search_grounding_available:
        grounded_config = types.GenerateContentConfig(
            system_instruction=effective_instruction,
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
        system_instruction=effective_instruction,
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
