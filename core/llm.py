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

# Default primary model and ordered rotation candidates for free-tier resilience
DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_ROTATION_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
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
    """
    llm_client = client or get_gemini_client()
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
                    await record_usage(response, model_name, feature, chat_id, user_id)
                    return text, model_name
            logger.warning(f"Model {model_name} returned empty text for {feature}.")
        except Exception as exc:
            logger.warning(f"Model {model_name} failed for {feature}: {exc}. Rotating...")
            continue

    logger.error(f"All candidate models exhausted for feature: {feature}.")
    return None, None


async def generate_response(
    prompt: str,
    system_instruction: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a text response from the Gemini model."""
    if not prompt or not prompt.strip():
        return "Будь ласка, вкажіть повідомлення або запитання.", None

    active_persona = get_persona(persona_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction or active_persona.chat_system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    text, model = await execute_text_generation(
        prompt=prompt.strip(),
        config=config,
        candidates=get_candidate_models(),
        feature="chat",
        client=client,
        chat_id=chat_id,
        user_id=user_id,
    )
    return (text, model) if text else (API_ERROR_MESSAGE, None)


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


# System instruction for standup comedy roast persona in Ukrainian
ROAST_SYSTEM_INSTRUCTION = (
    "Ти саркастичний, гострий на язик, але доброзичливий стендап-комік. "
    "Твоє завдання — зробити дотепний, смішний і колоритний дружній 'прожар' (роаст) користувача. "
    "Жартуй яскраво, доброзичливою іронією та сарказмом. "
    "Якщо надані останні повідомлення користувача в чаті, обов'язково обіграй їхні теми або манеру спілкування. "
    "Ти ЗАВЖДИ відповідаєш виключно українською мовою. "
    "Не пиши більше ніж 6 речень."
)


def _build_roast_prompt(
    clean_target: str,
    context_messages: Optional[list[str]],
    is_meme_lord: bool,
) -> str:
    """Formats the prompt context for standup comedy or meme-lord roasts."""
    quotes = "\n".join(f"- {msg}" for msg in context_messages) if context_messages else None

    if is_meme_lord:
        if quotes:
            return (
                f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
                f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
                "Обіграй ці цитати через актуальні меми, жизу, базу, крінж або щитпостинг (1-3 абзаци). "
                "Відповідай виключно українською мовою."
            )
        return (
            f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
            "Цей мембер поки що взагалі мовчить у чаті (мабуть, ловить крінж або боїться спалитися). "
            "Пожартуй над цим у стилі щитпостингу та постиронії (1-2 абзаци). "
            "Відповідай виключно українською мовою."
        )

    if quotes:
        return (
            f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
            f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
            "Обіграй ці цитати або звички у короткій, смішній стендап-прожарці (1-3 абзаци). "
            "Відповідай виключно українською мовою."
        )
    return (
        f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
        "Цей користувач поки що майже нічого не писав у цьому чаті (або майстерно ховається у засідці). "
        "Пожартуй над цим у короткій стендап-прожарці (1-2 абзаци). "
        "Відповідай виключно українською мовою."
    )


async def generate_roast(
    target_name: str,
    context_messages: Optional[list[str]] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Generates a witty standup comedy roast of a user in Ukrainian."""
    clean_target = target_name.lstrip("@").strip()
    active_persona = get_persona(persona_key)
    prompt = _build_roast_prompt(
        clean_target=clean_target,
        context_messages=context_messages,
        is_meme_lord=(active_persona.key == "meme_lord"),
    )

    config = types.GenerateContentConfig(
        system_instruction=active_persona.roast_system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    text, model = await execute_text_generation(
        prompt=prompt,
        config=config,
        candidates=get_candidate_models(),
        feature="roast",
        client=client,
        chat_id=chat_id,
        user_id=user_id,
    )
    return (text, model) if text else (API_ERROR_MESSAGE, None)



IMAGE_ERROR_MESSAGE = (
    "Вибачте, не вдалося згенерувати зображення через штучний інтелект. "
    "Будь ласка, спробуйте ще раз пізніше або змініть опис."
)


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
                await record_usage(response, model_name, "meme", chat_id, user_id)
                return data, mime, None, model_name
            logger.warning(f"Image model {model_name} returned no image parts.")
        except Exception as exc:
            logger.warning(f"Image generation with {model_name} failed: {exc}. Trying next candidate...")
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

    prompt = _build_reaction_prompt(current_message, chat_history, author_name)
    config = types.GenerateContentConfig(
        system_instruction=_build_reaction_system_instruction(persona_key),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    llm_client = client or get_gemini_client()

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
            if raw in ALLOWED_TELEGRAM_REACTIONS:
                return raw, model_name
            logger.info(f"Model {model_name} suggested invalid or unwhitelisted reaction: {raw}")
            return None, model_name
        except Exception as exc:
            logger.warning(f"Reaction evaluation with {model_name} failed: {exc}. Trying next...")
            continue

    logger.error("All candidate reaction models exhausted.")
    return None, None
