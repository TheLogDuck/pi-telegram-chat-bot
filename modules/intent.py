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
    PERSONA = auto()
    LANGUAGE = auto()
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
        # Canonical slash & trigger
        "roast", "roasts", "roasted", "roasting", "roaster",
        "burn", "burns", "burned", "burning",
        "mock", "mocks", "mocking",
        "diss", "disses", "dissed", "dissing",
        "drag", "drags", "dragged", "dragging",
        "flame", "flames", "flamed", "flaming",
        "grill", "grills", "grilled", "grilling",
        "cook", "cooks", "cooked", "cooking",
        "destroy", "destroys", "shred", "insult", "insults", "ridicule",
        # German roast triggers & colloquial slang
        "roaste", "roasten", "roastest", "geroastet",
        "röste", "rösten", "röstet", "geröstet",
        "dissen", "diss", "disse", "disst", "gedisst",
        "verspotten", "verspotte", "verspottet",
        "fertigmachen", "zerlege", "zerlegen", "zerleg", "zerlegt",
        "niedermachen", "beleidigen", "beleidige", "beleidigt",
        "grillen", "grille", "braten", "brate",
        # Ukrainian canonical & colloquial slang
        "просмаж", "просмажити", "просмажка", "просмажте", "просмажуй",
        "підсмаж", "підсмажити", "підсмажка", "підсмажуй",
        "рознеси", "рознести", "рознос", "розноси", "рознесіть",
        "постіби", "постібися", "постібись", "постьоб", "стьоб", "стеб",
        "вистеби", "вистіби", "висмій", "висміяти", "висміюй", "поглузуй", "глузуй",
        "підколи", "підколоти", "підкол", "підколюй", "підколіть",
        "затроль", "затролити", "потроль", "потролити", "тролінг", "троль",
        "попусти", "попустити", "розвали", "розвалити", "розмаж", "розмазати",
        "обісри", "захейти", "захейтити", "закрінжуй", "закринжуй",
        "спали", "спалити", "підпали", "підпалити", "спопели", "спопелити",
        "зачмири", "зачмирити", "почмири", "зганьби", "зганьбити", "присороми",
        "розірви", "розірвати",
        # Russian canonical & colloquial slang
        "прожарь", "прожарить", "прожарка", "прожарьте",
        "поджарь", "поджарить", "поджарьте",
        "роаст", "роасти", "роастить", "зароасти", "зароасть", "роастинг",
        "разнеси", "разнести", "разнос", "разнесите",
        "постеби", "постебись", "стеб", "стёб", "выстеби",
        "высмей", "высмеять", "высмеивать", "поглумись", "глумись",
        "подколи", "подколоть", "подкол", "подколите", "подкалывать",
        "затролль", "затроллить", "потролль", "потроллить", "троллинг", "тролль",
        "опусти", "опустить", "опустите",
        "развали", "развалить", "размажь", "размазать", "размажьте",
        "обосри", "обосрать", "закринжуй",
        "сожги", "сжечь", "испепели", "испепелить",
        "зачмори", "зачморить", "почмори", "опозорь", "опозорить", "пристыди",
        "разорви", "разорвать",
        # Common typos & phonetic variants
        "просмаш", "прожар", "зарости",
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
        # Canonical slash & trigger keyword
        "meme", "memes", "mem", "mems",
        # English creation verbs & visual media
        "pic", "pics", "picture", "pictures", "image", "images", "photo", "photos",
        "draw", "drawing", "draws", "drawn", "generate", "create", "illustration", "illustrations",
        "artwork", "sketch", "sketches", "comic", "comics", "render", "rendering",
        "paint", "painting", "visualize", "caricature", "wallpaper",
        # German creation verbs & visual media
        "bild", "bilder", "foto", "fotos", "grafik", "grafiken", "zeichnung", "zeichnungen",
        "generiere", "generieren", "erstelle", "erstellen", "erstell",
        "zeichne", "zeichnen", "male", "malen", "gemalt",
        "witzbild", "scherzbild", "lustiges", "karikatur", "karikaturen",
        "skizze", "skizzen", "gemälde", "porträt", "portrait", "comic",
        # Ukrainian & Russian memes / humor slang
        "мем", "меми", "мемы", "мемчик", "мемчики", "мемас", "мемаси", "мемасы", "мемасик", "мемасики",
        "мемес", "мемєс", "жаба", "жабу", "жабка", "жабку", "фотожаба", "фотожабу", "фотожабы",
        "демотиватор", "демотиватори", "демотиваторы", "демот", "демоти",
        # Visual media & art slang (Ukrainian & Russian)
        "картинка", "картинку", "картинки", "картиночка", "картиночку",
        "пікча", "пікчу", "пікчі", "пікчера", "пікчура",
        "пикча", "пикчу", "пикчи", "пикчер", "пикчера", "пикчура",
        "зображення", "зображ", "ілюстрація", "ілюстрацію", "иллюстрация", "иллюстрацию",
        "арт", "арти", "арты", "артік", "артик", "артець", "артец",
        "малюнок", "малюночок", "рисунок", "рисуночек",
        "фотка", "фотку", "фотки", "фоточка", "фоточку",
        "комікс", "комікси", "комикс", "комиксы",
        "карикатура", "карикатуру", "карикатури", "карикатуры", "шарж", "шаржи",
        "скетч", "скетчі", "скетчи",
        # Drawing & generation action verbs / slang commands
        "намалюй", "намалювати", "змалюй", "змалювати", "нарисуй", "нарисовать",
        "згенеруй", "згенери", "згенерувати", "сгенерируй", "сгенери", "сгенерить",
        "запили", "збацай", "забацай", "замути", "сваргань", "зліпи", "налепи",
        "наклепай", "накидай", "набросай", "наваяй", "изобрази", "відтвори",
        "відрендери", "отрендери", "візуалізуй", "визуализируй",
    ],
    IntentType.PERSONA: [
        "persona", "персона", "персони", "персону", "персонаж",
    ],
    IntentType.LANGUAGE: [
        "lang", "language", "мова", "мову", "язык", "sprache",
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

    # If no explicit @ was found, check words following a roast keyword
    tokens = text.split()
    for i, token in enumerate(tokens):
        clean_token = token.lower().strip("!?,.")
        if clean_token in INTENT_KEYWORDS[IntentType.ROAST]:
            for j in range(i + 1, len(tokens)):
                candidate = tokens[j].strip("!?,.")
                # Skip prepositions, articles, and courtesy words across all supported languages
                if candidate.lower() not in {
                    # Ukrainian & Russian prepositions / conjunctions / courtesy words
                    "на", "про", "над", "під", "под", "для", "з", "со", "за",
                    "цього", "этого", "цьому", "этому", "будь", "ласка", "пожалуйста", "пліз", "плиз",
                    # English prepositions, articles & courtesy words
                    "about", "for", "against", "at", "the", "a", "an", "this", "that", "please",
                    # German prepositions, articles & courtesy words
                    "über", "uber", "fuer", "für", "auf", "an", "den", "die", "das", "dem", "des",
                    "einen", "ein", "eine", "dieser", "diesen", "diesem", "dieses", "bitte",
                }:
                    return f"@{candidate.lstrip('@')}"
    return None


def extract_news_topic(text: str, matched_trigger: str) -> Optional[str]:
    """Extracts the subject topic for a news briefing after removing the trigger word."""
    # Remove the matched trigger keyword from the text
    pattern = rf"\b{re.escape(matched_trigger)}\b"
    remainder = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Clean punctuation and iteratively strip common conversational filler words
    cleaned = remainder.strip("!?,. :")
    filler_pattern = r"^(останні|останніх|свежие|последние|latest|the|über|uber|про|о|об|about)\s+"
    while re.search(filler_pattern, cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    return cleaned if cleaned else None


def extract_meme_prompt(text: str, matched_trigger: str) -> Optional[str]:
    """Extracts the visual description for a meme/image by removing trigger words."""
    pattern = rf"\b{re.escape(matched_trigger)}\b"
    remainder = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Strip punctuation and common request prefixes across Ukrainian, Russian, English, and German
    cleaned = remainder.strip("!?,. :")
    filler_pattern = (
        r"^(будь ласка|пліз|плиз|пожалуйста|мені|нам|мне|про|про те як|про те що|"
        r"про то как|про то что|про те|про то|з|зі|со|с|на тему|як|как|для|"
        r"зроби|сделай|покажи|намалюй|нарисуй|створи|создай|згенеруй|сгенерируй|"
        r"запили|забацай|збацай|замути|сваргань|наклепай|набросай|наваяй|"
        r"картинку|картинка|картинки|пікчу|пікча|пикчу|пикча|арт|зображення|изображение|"
        r"малюнок|рисунок|фото|фотку|фотожабу|жабу|мем|меми|мемы|мемчик|мемас|мемасик|"
        r"смішний|смішного|смешной|смешного|веселий|веселый|"
        r"please|pls|make|generate|draw|create|show|give me|paint|render|"
        r"a meme about|a meme of|meme about|meme of|a meme|meme|"
        r"a picture of|picture of|a pic of|pic of|an image of|image of|a photo of|photo of|"
        r"picture|pic|image|photo|comic|drawing|painting|"
        r"about|of|for|with|a|an|the|"
        r"bitte|generiere|erstelle|erstell|mach|mache|zeige|zeig|male|mal|zeichne|"
        r"ein meme über|ein meme von|meme über|meme von|einen meme über|einen meme von|"
        r"ein bild über|ein bild von|bild über|bild von|ein foto von|foto von|"
        r"bild|bilder|foto|fotos|grafik|grafiken|zeichnung|zeichnungen|"
        r"lustiges|lustige|lustigen|witziges|witzige|witzigen|"
        r"ein|eine|einen|einem|einer|der|die|das|den|dem|des|"
        r"über|von|fuer|für)\s+"
    )
    while re.search(filler_pattern, cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE).strip("!?,. :")

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
        # Cutoff 0.80 prevents false positives between Slavic words sharing prefixes (e.g. розкажи vs розмаж)
        matches = difflib.get_close_matches(token, ALL_KEYWORDS, n=1, cutoff=0.80)
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
