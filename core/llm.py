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
) -> str:
    """Asynchronously generates a text response from the Gemini model.

    Args:
        prompt: The user query or conversation context.
        system_instruction: Optional override for the bot persona instruction.
        client: Optional injected client (useful for unit testing and mocking).

    Returns:
        The generated response string in Ukrainian, or a friendly error message.
    """
    if not prompt or not prompt.strip():
        return "Будь ласка, вкажіть повідомлення або запитання."

    # Select model from environment or fallback to default
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    sys_instruction = system_instruction or DEFAULT_SYSTEM_INSTRUCTION
    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(system_instruction=sys_instruction)

    # Rotate through candidates to handle 404 deprecation or 429/503 spikes seamlessly
    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt.strip(),
                config=config,
            )
            if response and response.text:
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
) -> str:
    """Asynchronously generates a news briefing grounded with Google Search.

    Rotates through candidate models if rate limits or unavailable errors occur.

    Args:
        topic: Optional subject filter (e.g. 'технології', 'штучний інтелект').
        client: Optional injected client for unit testing.

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

    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(
        system_instruction=NEWS_SYSTEM_INSTRUCTION,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )

    # Rotate through candidates for resilient grounded search execution
    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
            logger.warning(f"Model {model_name} returned empty text for news briefing.")
        except Exception as exc:
            logger.warning(
                f"Grounded search with model {model_name} failed: {exc}. "
                "Rotating to next candidate model..."
            )
            continue

    # Fallback to standard model synthesis if Google Search tool quota is exhausted (Free Tier)
    logger.info("Search tool quota unavailable on Free Tier. Falling back to standard AI synthesis...")
    standard_config = types.GenerateContentConfig(
        system_instruction=NEWS_SYSTEM_INSTRUCTION,
    )
    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=standard_config,
            )
            if response and response.text:
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
) -> str:
    """Generates a witty standup comedy roast of a user in Ukrainian.

    Args:
        target_name: The username or display name of the user being roasted.
        context_messages: Optional recent messages sent by the user for context.
        client: Optional injected Gemini client for unit testing.

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
    )

    for model_name in get_candidate_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
            logger.warning(f"Model {model_name} returned empty roast text.")
        except Exception as exc:
            logger.warning(f"Roast generation with {model_name} failed: {exc}")
            continue

    logger.error("All candidate models failed during roast generation.")
    return API_ERROR_MESSAGE
