# Core LLM module providing non-blocking asynchronous access to Google's Gemini models.
# Designed for Raspberry Pi 3B+ to maintain a tiny memory footprint (<5 MB).
import os
from typing import Optional
from google import genai
from google.genai import types
from core.logger import setup_logger

logger = setup_logger("llm")

# Default model configuration; can be overridden via GEMINI_MODEL env var
DEFAULT_MODEL = "gemini-2.5-flash"

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

    try:
        # Use provided client or initialize a new one
        llm_client = client or get_gemini_client()

        # GenerateContentConfig configures generation parameters like system instructions
        config = types.GenerateContentConfig(
            system_instruction=sys_instruction,
        )

        # Call the asynchronous API namespace (.aio) so the event loop is never blocked
        response = await llm_client.aio.models.generate_content(
            model=model_name,
            contents=prompt.strip(),
            config=config,
        )

        # Extract text content safely
        if response and response.text:
            return response.text.strip()

        logger.warning("Gemini returned an empty response text.")
        return API_ERROR_MESSAGE

    except Exception as exc:
        # Catch network timeouts, invalid keys, or quota errors without crashing the bot
        logger.error(f"Error communicating with Gemini API: {exc}")
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

    Args:
        topic: Optional subject filter (e.g. 'технології', 'штучний інтелект').
        client: Optional injected client for unit testing.

    Returns:
        Structured news briefing in Ukrainian, or a friendly error message.
    """
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

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

    try:
        llm_client = client or get_gemini_client()

        # Configure Google Search grounding tool to retrieve live real-time news
        config = types.GenerateContentConfig(
            system_instruction=NEWS_SYSTEM_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        response = await llm_client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        if response and response.text:
            return response.text.strip()

        logger.warning("Gemini returned empty text for news briefing.")
        return API_ERROR_MESSAGE

    except Exception as exc:
        logger.error(f"Error generating grounded news briefing: {exc}")
        return API_ERROR_MESSAGE
