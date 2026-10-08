# Intent detection module: classifies incoming user messages into actionable commands.
# Supports Ukrainian, Russian, and English triggers with fuzzy typo tolerance via difflib.
from dataclasses import dataclass
from enum import Enum, auto
import difflib
import re
from typing import Dict, List, Optional


class IntentType(Enum):
    """Categorizes the user's intent to route to the correct bot action."""
    ROAST = auto()
    NEWS = auto()
    PING = auto()
    HELP = auto()
    STATS = auto()
    MEME = auto()
    CHAT = auto()  # General conversational fallback for Gemini AI


@dataclass
class IntentResult:
    """Encapsulates the detected intent and any parsed arguments."""
    intent: IntentType
    confidence: float
    target_user: Optional[str] = None
    topic: Optional[str] = None
    raw_query: str = ""


# Canonical keywords for each intent across Ukrainian, Russian, and English
INTENT_KEYWORDS: Dict[IntentType, List[str]] = {
    IntentType.ROAST: [
        "roast", "просмаж", "просмажити", "зароасти", "зароасть",
        "прожарь", "прожарить", "роаст", "прожар", "просмаш", "зарости",
    ],
    IntentType.NEWS: [
        "news", "новини", "новина", "новинки", "новости", "новость",
        "дайджест", "брифінг", "брифинг", "briefing",
    ],
    IntentType.PING: [
        "ping", "пінг", "пинг", "pong", "понг",
    ],
    IntentType.HELP: [
        "help", "допомога", "довідка", "помощь", "справка", "команди", "команды", "commands",
    ],
    IntentType.STATS: [
        "stats", "статистика", "стата", "статы", "statistics",
    ],
    IntentType.MEME: [
        "meme", "мем", "мемчик", "мемас", "мемасик",
    ],
}

# Inverted mapping to quickly look up which intent a matching keyword belongs to
KEYWORD_TO_INTENT: Dict[str, IntentType] = {
    kw: intent for intent, kws in INTENT_KEYWORDS.items() for kw in kws
}
ALL_KEYWORDS: List[str] = list(KEYWORD_TO_INTENT.keys())


def extract_target_user(text: str) -> Optional[str]:
    """Finds a target username (@username or word) for roast commands."""
    # First search for explicit @username mentions
    mention_match = re.search(r"@([a-zA-Z0-9_]{3,32})", text)
    if mention_match:
        return f"@{mention_match.group(1)}"

    # If no explicit @ was found, check if a word follows a roast keyword
    tokens = text.split()
    for i, token in enumerate(tokens):
        clean_token = token.lower().strip("!?,.")
        if clean_token in INTENT_KEYWORDS[IntentType.ROAST] and i + 1 < len(tokens):
            candidate = tokens[i + 1].strip("!?,.")
            # Ignore common prepositions
            if candidate.lower() not in {"на", "про", "about", "for"}:
                return f"@{candidate.lstrip('@')}"
    return None


def extract_news_topic(text: str, matched_trigger: str) -> Optional[str]:
    """Extracts the subject topic for a news briefing after removing the trigger word."""
    # Remove the matched trigger keyword from the text
    pattern = rf"\b{re.escape(matched_trigger)}\b"
    remainder = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Clean punctuation and iteratively strip common conversational filler words
    cleaned = remainder.strip("!?,. :")
    filler_pattern = r"^(останні|останніх|свежие|последние|latest|the|про|о|об|about)\s+"
    while re.search(filler_pattern, cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    return cleaned if cleaned else None


def extract_meme_prompt(text: str, matched_trigger: str) -> Optional[str]:
    """Extracts the visual description for a meme by removing trigger words."""
    pattern = rf"\b{re.escape(matched_trigger)}\b"
    remainder = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Strip punctuation and common request prefixes
    cleaned = remainder.strip("!?,. :")
    filler_pattern = r"^(про|про те як|про те що|про те|about|of|з|со|с|на тему|зроби|намалюй|створи|згенеруй|generate|make|create)\s+"
    while re.search(filler_pattern, cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    return cleaned if cleaned else None



def detect_intent(text: str) -> IntentResult:
    """Classifies user text into an IntentResult using exact and fuzzy matching.

    Args:
        text: The cleaned message text (with bot mentions already stripped).

    Returns:
        IntentResult containing the matched intent, confidence, and parameters.
    """
    if not text or not text.strip():
        return IntentResult(intent=IntentType.CHAT, confidence=1.0, raw_query="")

    query = text.strip()
    lower_query = query.lower()

    # 1. Direct slash command handling (/roast, /news, /ping, etc.)
    if lower_query.startswith("/"):
        cmd_part = lower_query.split()[0].lstrip("/")
        # Handle command names like roast@bot_name
        base_cmd = cmd_part.split("@")[0]

        if base_cmd == "roast":
            return IntentResult(
                intent=IntentType.ROAST,
                confidence=1.0,
                target_user=extract_target_user(query),
                raw_query=query,
            )
        elif base_cmd == "news":
            tokens = query.split(maxsplit=1)
            topic = tokens[1].strip() if len(tokens) > 1 else None
            return IntentResult(
                intent=IntentType.NEWS,
                confidence=1.0,
                topic=topic,
                raw_query=query,
            )
        elif base_cmd == "ping":
            return IntentResult(intent=IntentType.PING, confidence=1.0, raw_query=query)
        elif base_cmd == "help":
            return IntentResult(intent=IntentType.HELP, confidence=1.0, raw_query=query)
        elif base_cmd == "stats":
            return IntentResult(intent=IntentType.STATS, confidence=1.0, raw_query=query)
        elif base_cmd == "meme":
            tokens = query.split(maxsplit=1)
            prompt = tokens[1].strip() if len(tokens) > 1 else None
            return IntentResult(
                intent=IntentType.MEME,
                confidence=1.0,
                topic=prompt,
                raw_query=query,
            )

    # 2. Tokenize query into clean words for natural language matching
    tokens = [re.sub(r"[^\wа-яА-ЯіїєґІЇЄҐёЁ]", "", tok.lower()) for tok in query.split()]
    tokens = [t for t in tokens if t]

    # Check for exact keyword hits
    for token in tokens:
        if token in KEYWORD_TO_INTENT:
            matched_intent = KEYWORD_TO_INTENT[token]
            if matched_intent == IntentType.ROAST:
                return IntentResult(
                    intent=IntentType.ROAST,
                    confidence=1.0,
                    target_user=extract_target_user(query),
                    raw_query=query,
                )
            elif matched_intent == IntentType.NEWS:
                return IntentResult(
                    intent=IntentType.NEWS,
                    confidence=1.0,
                    topic=extract_news_topic(query, token),
                    raw_query=query,
                )
            elif matched_intent == IntentType.MEME:
                return IntentResult(
                    intent=IntentType.MEME,
                    confidence=1.0,
                    topic=extract_meme_prompt(query, token),
                    raw_query=query,
                )
            else:
                return IntentResult(intent=matched_intent, confidence=1.0, raw_query=query)

    # 3. Fuzzy matching using Python difflib for typos (e.g. просмаш, зарости)
    for token in tokens:
        matches = difflib.get_close_matches(token, ALL_KEYWORDS, n=1, cutoff=0.75)
        if matches:
            best_match = matches[0]
            matched_intent = KEYWORD_TO_INTENT[best_match]

            if matched_intent == IntentType.ROAST:
                return IntentResult(
                    intent=IntentType.ROAST,
                    confidence=0.85,
                    target_user=extract_target_user(query),
                    raw_query=query,
                )
            elif matched_intent == IntentType.NEWS:
                return IntentResult(
                    intent=IntentType.NEWS,
                    confidence=0.85,
                    topic=extract_news_topic(query, token),
                    raw_query=query,
                )
            elif matched_intent == IntentType.MEME:
                return IntentResult(
                    intent=IntentType.MEME,
                    confidence=0.85,
                    topic=extract_meme_prompt(query, best_match),
                    raw_query=query,
                )
            else:
                return IntentResult(intent=matched_intent, confidence=0.85, raw_query=query)

    # 4. Default: No command intent matched, forward to Gemini for open conversation
    return IntentResult(intent=IntentType.CHAT, confidence=1.0, raw_query=query)
