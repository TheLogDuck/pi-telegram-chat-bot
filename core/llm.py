# Core LLM module providing non-blocking asynchronous access to Google's Gemini models.
# Designed for Raspberry Pi 3B+ to maintain a tiny memory footprint (<5 MB).
import os
from typing import Optional
from google import genai
from google.genai import types
from core.logger import setup_logger

logger = setup_logger("llm")

# Default primary model and ordered rotation candidates for free-tier resilience
DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_ROTATION_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]

# Track whether Google Search tool quota is available on this API key.
# On Free Tier accounts, this disables cleanly on the first 429 to avoid retry storms.
_search_grounding_available = os.getenv("ENABLE_SEARCH_GROUNDING", "true").lower() in ("true", "1", "yes")

# Flash model pay-as-you-go rates per 1,000,000 tokens (USD)
FLASH_INPUT_COST_PER_MILLION = 0.10
FLASH_OUTPUT_COST_PER_MILLION = 0.40


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
        from core.db import async_save_token_usage

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



def get_candidate_models() -> list[str]:
    """Returns ordered list of models for automatic failover and quota rotation."""
    configured = os.getenv("GEMINI_MODEL")
    if configured:
        return [configured] + [m for m in MODEL_ROTATION_CANDIDATES if m != configured]
    return list(MODEL_ROTATION_CANDIDATES)

# System instruction enforces understanding UA/RU/EN while speaking strictly in Ukrainian
DEFAULT_SYSTEM_INSTRUCTION = (
    "Ти корисний, кмітливий та дотепний Telegram-бот. "
    "Ти вільно розумієш запити користувачів українською, російською та англійською мовами. "
    "Проте свої власні відповіді ти ЗАВЖДИ формулюєш виключно українською мовою. "
    "Твої відповіді мають бути чіткими, лаконічними та природними."
)

# Friendly fallback message in Ukrainian when the Gemini API cannot be reached
API_ERROR_MESSAGE = (
    "Вибачте, сталася помилка під час обробки вашого запиту через штучний інтелект. "
    "Будь ласка, спробуйте ще раз пізніше."
)


def get_gemini_client() -> genai.Client:
    """Instantiates the Google GenAI client using the configured API key.

    We avoid storing persistent heavy state in memory. The client object
    is lightweight and delegates async network calls efficiently.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not defined in the environment.")
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    # Return configured genai client
    return genai.Client(api_key=api_key)


async def generate_response(
    prompt: str,
    system_instruction: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> str:
    """Asynchronously generates a text response from the Gemini model.

    Args:
        prompt: The user query or conversation context.
        system_instruction: Optional override for the bot persona instruction.
        client: Optional injected client (useful for unit testing and mocking).
        chat_id: Optional Telegram chat identifier for telemetry attribution.
        user_id: Optional Telegram user identifier for telemetry attribution.

    Returns:
        The generated response string in Ukrainian, or a friendly error message.
    """
    if not prompt or not prompt.strip():
        return "Будь ласка, вкажіть повідомлення або запитання."

    # Select model from environment or fallback to default
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    sys_instruction = system_instruction or DEFAULT_SYSTEM_INSTRUCTION
    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(
        system_instruction=sys_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Rotate through candidates to handle 404 deprecation or 429/503 spikes seamlessly
    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt.strip(),
                config=config,
            )
            if response and response.text:
                # Log token usage asynchronously to avoid blocking user response
                await record_usage(response, model_name, "chat", chat_id, user_id)
                return response.text.strip()
            logger.warning(f"Model {model_name} returned empty text.")
        except Exception as exc:
            logger.warning(
                f"Model {model_name} encountered an error: {exc}. "
                "Rotating to next fallback model..."
            )
            continue

    logger.error("All Gemini model candidates exhausted.")
    return API_ERROR_MESSAGE


# System instruction specifically for grounding news briefings in Ukrainian
NEWS_SYSTEM_INSTRUCTION = (
    "Ти професійний новинний оглядач. "
    "Створюй перевірені, структуровані та лаконічні дайджести новин виключно українською мовою. "
    "Форматуй відповідь у вигляді 3-5 головних новин з короткими тезами."
)


async def generate_news_briefing(
    topic: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> str:
    """Asynchronously generates a news briefing grounded with Google Search.

    Rotates through candidate models if rate limits or unavailable errors occur.

    Args:
        topic: Optional subject filter (e.g. 'технології', 'штучний інтелект').
        client: Optional injected client for unit testing.
        chat_id: Optional Telegram chat identifier for telemetry attribution.
        user_id: Optional Telegram user identifier for telemetry attribution.

    Returns:
        Structured news briefing in Ukrainian, or a friendly error message.
    """
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
    llm_client = client or get_gemini_client()

    # Attempt Grounded Search with Google Search tool only if quota is available
    if _search_grounding_available:
        config = types.GenerateContentConfig(
            system_instruction=NEWS_SYSTEM_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        for model_name in get_candidate_models():
            try:
                response = await llm_client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    await record_usage(response, model_name, "news", chat_id, user_id)
                    return response.text.strip()
                logger.warning(f"Model {model_name} returned empty text for news briefing.")
            except Exception as exc:
                exc_str = str(exc)
                if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                    logger.info("Search tool quota unavailable on Free Tier (429). Switching to standard AI synthesis.")
                    _search_grounding_available = False
                    break
                logger.warning(f"Grounded search with model {model_name} failed: {exc}. Trying next candidate...")
                continue

    # Fallback to standard model synthesis (fast, zero external tool quota requirement)
    standard_config = types.GenerateContentConfig(
        system_instruction=NEWS_SYSTEM_INSTRUCTION,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=standard_config,
            )
            if response and response.text:
                await record_usage(response, model_name, "news", chat_id, user_id)
                return response.text.strip()
        except Exception as exc:
            logger.warning(f"Standard news generation with {model_name} failed: {exc}")
            continue

    logger.error("All candidate models failed during news briefing.")
    return API_ERROR_MESSAGE


# System instruction for standup comedy roast persona in Ukrainian
ROAST_SYSTEM_INSTRUCTION = (
    "Ти саркастичний, гострий на язик, але доброзичливий стендап-комік. "
    "Твоє завдання — зробити дотепний, смішний і колоритний дружній 'прожар' (роаст) користувача. "
    "Жартуй яскраво, доброзичливою іронією та сарказмом. "
    "Якщо надані останні повідомлення користувача в чаті, обов'язково обіграй їхні теми або манеру спілкування. "
    "Ти ЗАВЖДИ відповідаєш виключно українською мовою. "
    "Не пиши більше ніж 6 речень."
)


async def generate_roast(
    target_name: str,
    context_messages: Optional[list[str]] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> str:
    """Generates a witty standup comedy roast of a user in Ukrainian.

    Args:
        target_name: The username or display name of the user being roasted.
        context_messages: Optional recent messages sent by the user for context.
        client: Optional injected Gemini client for unit testing.
        chat_id: Optional Telegram chat identifier for telemetry attribution.
        user_id: Optional Telegram user identifier for telemetry attribution.

    Returns:
        A humorous roast in Ukrainian, or a friendly fallback message on failure.
    """
    clean_target = target_name.lstrip("@").strip()
    if context_messages:
        quotes = "\n".join(f"- {msg}" for msg in context_messages)
        prompt = (
            f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
            f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
            "Обіграй ці цитати або звички у короткій, смішній стендап-прожарці (1-3 абзаци). "
            "Відповідай виключно українською мовою."
        )
    else:
        prompt = (
            f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
            "Цей користувач поки що майже нічого не писав у цьому чаті (або майстерно ховається у засідці). "
            "Пожартуй над цим у короткій стендап-прожарці (1-2 абзаци). "
            "Відповідай виключно українською мовою."
        )

    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(
        system_instruction=ROAST_SYSTEM_INSTRUCTION,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                await record_usage(response, model_name, "roast", chat_id, user_id)
                return response.text.strip()
            logger.warning(f"Model {model_name} returned empty roast text.")
        except Exception as exc:
            logger.warning(f"Roast generation with {model_name} failed: {exc}")
            continue

    logger.error("All candidate models failed during roast generation.")
    return API_ERROR_MESSAGE
