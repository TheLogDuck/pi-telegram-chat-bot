# Core LLM module providing non-blocking asynchronous access to Google's Gemini models.
# Designed for Raspberry Pi 3B+ to maintain a tiny memory footprint (<5 MB).
import os
from typing import Optional
from google import genai
from google.genai import types
from core.logger import setup_logger
from core.personas import get_persona

logger = setup_logger("llm")

# Whitelist of standard Telegram reaction emojis supported across free chats
ALLOWED_TELEGRAM_REACTIONS: frozenset[str] = frozenset({
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱",
    "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡",
    "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "🍿", "☕", "🍸",
    "🍩", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨", "🤝", "✍",
    "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪", "🗿", "🆒", "💘",
    "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️", "🤷", "🤷‍♀️", "😡",
})

# Permissive safety settings for 18+ cynical/dark humor persona to prevent API false-positive blocks
CYNIC_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]

# Default primary model and ordered rotation candidates for free-tier resilience
DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_ROTATION_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]

# Image generation models ("Nano Banana" series from Google DeepMind)
# Ordered strictly from cheapest to priciest per image
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-lite-image"
IMAGE_MODEL_ROTATION_CANDIDATES = [
    "gemini-3.1-flash-lite-image",
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
]


def get_candidate_image_models() -> list[str]:
    """Returns ordered list of Nano Banana image models for failover rotation."""
    configured = os.getenv("GEMINI_IMAGE_MODEL")
    if configured:
        return [configured] + [m for m in IMAGE_MODEL_ROTATION_CANDIDATES if m != configured]
    return list(IMAGE_MODEL_ROTATION_CANDIDATES)


# Reaction models: strictly prioritized by cheapest token cost and low latency
DEFAULT_REACTION_MODEL = "gemini-3.5-flash-lite"
REACTION_MODEL_ROTATION_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
]



def get_candidate_reaction_models() -> list[str]:
    """Returns ordered list of lightweight models for reaction evaluation."""
    configured = os.getenv("GEMINI_REACTION_MODEL")
    if configured:
        return [configured] + [m for m in REACTION_MODEL_ROTATION_CANDIDATES if m != configured]
    return list(REACTION_MODEL_ROTATION_CANDIDATES)



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
    persona_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a text response from the Gemini model.

    Args:
        prompt: The user query or conversation context.
        system_instruction: Optional override for the bot persona instruction.
        client: Optional injected client (useful for unit testing and mocking).
        chat_id: Optional Telegram chat identifier for telemetry attribution.
        user_id: Optional Telegram user identifier for telemetry attribution.
        persona_key: Optional persona identifier ('standard', 'cynic', etc.).

    Returns:
        A tuple of (response_text, model_name) where model_name is None on error.
    """
    if not prompt or not prompt.strip():
        return "Будь ласка, вкажіть повідомлення або запитання.", None

    # Resolve active persona instruction and corresponding safety filters
    active_persona = get_persona(persona_key)
    sys_instruction = system_instruction or active_persona.chat_system_instruction
    safety_settings = CYNIC_SAFETY_SETTINGS if active_persona.key == "cynic" else None

    # Select model from environment or fallback to default
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(
        system_instruction=sys_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        safety_settings=safety_settings,
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
                return response.text.strip(), model_name
            logger.warning(f"Model {model_name} returned empty text.")
        except Exception as exc:
            logger.warning(
                f"Model {model_name} encountered an error: {exc}. "
                "Rotating to next fallback model..."
            )
            continue

    logger.error("All Gemini model candidates exhausted.")
    return API_ERROR_MESSAGE, None


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
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a news briefing grounded with Google Search.

    Rotates through candidate models if rate limits or unavailable errors occur.

    Args:
        topic: Optional subject filter (e.g. 'технології', 'штучний інтелект').
        client: Optional injected client for unit testing.
        chat_id: Optional Telegram chat identifier for telemetry attribution.
        user_id: Optional Telegram user identifier for telemetry attribution.

    Returns:
        A tuple of (news_text, model_name) where model_name is None on error.
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
                    return response.text.strip(), model_name
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
                return response.text.strip(), model_name
        except Exception as exc:
            logger.warning(f"Standard news generation with {model_name} failed: {exc}")
            continue

    logger.error("All candidate models failed during news briefing.")
    return API_ERROR_MESSAGE, None


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
    persona_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Generates a witty or savage standup comedy roast of a user in Ukrainian.

    Args:
        target_name: The username or display name of the user being roasted.
        context_messages: Optional recent messages sent by the user for context.
        client: Optional injected Gemini client for unit testing.
        chat_id: Optional Telegram chat identifier for telemetry attribution.
        user_id: Optional Telegram user identifier for telemetry attribution.
        persona_key: Optional persona key ('standard' or 'cynic').

    Returns:
        A tuple of (roast_text, model_name) where model_name is None on failure.
    """
    clean_target = target_name.lstrip("@").strip()
    active_persona = get_persona(persona_key)
    is_cynic = active_persona.key == "cynic"

    if is_cynic:
        if context_messages:
            quotes = "\n".join(f"- {msg}" for msg in context_messages)
            prompt = (
                f"Влаштуй гранично жорсткий, токсичний і нецензурний роаст користувача @{clean_target} з чорним гумором.\n"
                f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
                "Рознеси ці цитати або звички у нищівній, брудній прожарці з соковитими українськими матюками та сленгом (1-3 абзаци). "
                "Відповідай виключно українською мовою."
            )
        else:
            prompt = (
                f"Влаштуй гранично жорсткий, токсичний і нецензурний роаст користувача @{clean_target} з чорним гумором.\n"
                "Цей боягуз поки що майже нічого не писав у цьому чаті (або прикидається мертвим). "
                "Висмій це без жалю у брудній стендап-прожарці з соковитими українськими матюками та сленгом (1-2 абзаци). "
                "Відповідай виключно українською мовою."
            )
    elif active_persona.key == "meme_lord":
        if context_messages:
            quotes = "\n".join(f"- {msg}" for msg in context_messages)
            prompt = (
                f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
                f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
                "Обіграй ці цитати через актуальні меми, жизу, базу, крінж або щитпостинг (1-3 абзаци). "
                "Відповідай виключно українською мовою."
            )
        else:
            prompt = (
                f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
                "Цей мембер поки що взагалі мовчить у чаті (мабуть, ловить крінж або боїться спалитися). "
                "Пожартуй над цим у стилі щитпостингу та постиронії (1-2 абзаци). "
                "Відповідай виключно українською мовою."
            )
    else:
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
    safety_settings = CYNIC_SAFETY_SETTINGS if is_cynic else None
    config = types.GenerateContentConfig(
        system_instruction=active_persona.roast_system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        safety_settings=safety_settings,
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
                return response.text.strip(), model_name
            logger.warning(f"Model {model_name} returned empty roast text.")
        except Exception as exc:
            logger.warning(f"Roast generation with {model_name} failed: {exc}")
            continue

    logger.error("All candidate models failed during roast generation.")
    return API_ERROR_MESSAGE, None


IMAGE_ERROR_MESSAGE = (
    "Вибачте, не вдалося згенерувати зображення через штучний інтелект. "
    "Будь ласка, спробуйте ще раз пізніше або змініть опис."
)


async def generate_meme_image(
    prompt: str,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], Optional[str]]:
    """Generates an image/meme using Google's Nano Banana multimodal models.

    Args:
        prompt: User's visual prompt or concept description.
        client: Optional injected Gemini client for testing.
        chat_id: Optional Telegram chat identifier for telemetry.
        user_id: Optional Telegram user identifier for telemetry.
        persona_key: Optional persona identifier ('standard', 'cynic', etc.).

    Returns:
        A tuple of (image_bytes, mime_type, error_message, model_name).
    """
    if not prompt or not prompt.strip():
        return None, None, "Будь ласка, вкажіть опис для зображення.", None

    active_persona = get_persona(persona_key)
    full_prompt = active_persona.meme_prompt_template.format(prompt=prompt.strip())

    llm_client = client or get_gemini_client()
    safety_settings = CYNIC_SAFETY_SETTINGS if active_persona.key == "cynic" else None
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        safety_settings=safety_settings,
    )

    for model_name in get_candidate_image_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=config,
            )
            # Find the binary image part in response candidates
            if response and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.inline_data and part.inline_data.data:
                            # Record token consumption in SQLite for /stats
                            await record_usage(response, model_name, "meme", chat_id, user_id)
                            return part.inline_data.data, part.inline_data.mime_type, None, model_name

            logger.warning(f"Image model {model_name} returned no image parts.")
        except Exception as exc:
            logger.warning(
                f"Image generation with {model_name} failed: {exc}. Trying next candidate..."
            )
            continue

    logger.error("All Nano Banana image models exhausted.")
    return None, None, IMAGE_ERROR_MESSAGE, None


def _build_reaction_prompt(
    current_message: str,
    chat_history: list[dict],
    author_name: Optional[str] = None,
) -> str:
    """Formats the conversational context and current message for the reaction decision."""
    history_lines = []
    for item in chat_history:
        uname = item.get("username") or "User"
        txt = item.get("text", "").strip()
        if txt:
            history_lines.append(f"- {uname}: {txt}")

    context_block = "\n".join(history_lines) if history_lines else "(No previous messages)"
    author_label = author_name or "User"
    return (
        f"Context of recent chat messages:\n{context_block}\n\n"
        f"New message from {author_label}:\n\"{current_message.strip()}\"\n\n"
        "Decide: Should you react with an emoji, or NONE?"
    )


def _build_reaction_system_instruction(persona_key: Optional[str]) -> str:
    """Builds a system prompt instructing the model to pick ONE emoji or NONE."""
    persona = get_persona(persona_key)
    return (
        f"You are a Telegram bot with the following persona: {persona.name} ({persona.description}).\n"
        "Your task is to analyze the recent conversation and determine whether to react to the new message.\n"
        "RULES:\n"
        "1. Respond with EXACTLY ONE emoji from standard Telegram reactions, OR the word NONE.\n"
        "2. Only react if the message strongly warrants an emotional reaction fitting your persona. "
        "For ordinary chatter, greetings, or neutral statements, respond with NONE.\n"
        "3. Output ONLY the single emoji or NONE. No explanations, words, markdown, or punctuation."
    )


async def decide_message_reaction(
    current_message: str,
    chat_history: list[dict],
    persona_key: Optional[str] = None,
    author_name: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Evaluates whether to set an emoji reaction on a message based on context and persona."""
    if not current_message or not current_message.strip():
        return None, None

    active_persona = get_persona(persona_key)
    prompt = _build_reaction_prompt(current_message, chat_history, author_name)
    sys_instruction = _build_reaction_system_instruction(persona_key)
    safety_settings = CYNIC_SAFETY_SETTINGS if active_persona.key == "cynic" else None
    llm_client = client or get_gemini_client()
    config = types.GenerateContentConfig(
        system_instruction=sys_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        safety_settings=safety_settings,
    )

    for model_name in get_candidate_reaction_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            await record_usage(response, model_name, "reaction", chat_id, user_id)
            raw = (response.text or "").strip().strip("\"'").strip()
            if not raw or raw.upper() == "NONE":
                return None, model_name
            # Strictly validate that the emoji is supported by Telegram
            if raw in ALLOWED_TELEGRAM_REACTIONS:
                return raw, model_name
            logger.info(f"Model {model_name} suggested invalid or unwhitelisted reaction: {raw}")
            return None, model_name
        except Exception as exc:
            logger.warning(f"Reaction evaluation with {model_name} failed: {exc}. Trying next...")
            continue

    logger.error("All candidate reaction models exhausted.")
    return None, None






