# Central configuration and constants for the LLM domain.
# Contains model names, rotation candidate lists, cost constants, and standard system prompts.
import os

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

# Primary chat model and ordered rotation candidates for free-tier resilience
DEFAULT_MODEL = "gemini-3.8-flash"
MODEL_ROTATION_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
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


# Image generation models ("Nano Banana" series) ordered from cheapest to priciest
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


# Flash model pay-as-you-go rates per 1,000,000 tokens (USD)
FLASH_INPUT_COST_PER_MILLION = 0.10
FLASH_OUTPUT_COST_PER_MILLION = 0.40

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

# Friendly fallback message in Ukrainian when image generation fails
IMAGE_ERROR_MESSAGE = (
    "Вибачте, не вдалося згенерувати зображення через штучний інтелект. "
    "Будь ласка, спробуйте ще раз пізніше або змініть опис."
)

# System instruction specifically for grounding news briefings in Ukrainian
NEWS_SYSTEM_INSTRUCTION = (
    "Ти професійний новинний оглядач. "
    "Створюй перевірені, структуровані та лаконічні дайджести новин виключно українською мовою. "
    "Форматуй відповідь у вигляді 3-5 головних новин з короткими тезами."
)

# System instruction for standup comedy roast persona in Ukrainian
ROAST_SYSTEM_INSTRUCTION = (
    "Ти саркастичний, гострий на язик, але доброзичливий стендап-комік. "
    "Твоє завдання — зробити дотепний, смішний і колоритний дружній 'прожар' (роаст) користувача. "
    "Жартуй яскраво, доброзичливою іронією та сарказмом. "
    "Якщо надані останні повідомлення користувача в чаті, обов'язково обіграй їхні теми або манеру спілкування. "
    "Ти ЗАВЖДИ відповідаєш виключно українською мовою. "
    "Не пиши більше ніж 6 речень."
)
