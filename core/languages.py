# Language registry, directives for LLM prompting, and lightweight UI localization.
# Designed for Raspberry Pi 3B+ to maintain zero external library bloat (<10 KB RAM).
from typing import Dict

DEFAULT_LANGUAGE = "uk"

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "uk": "Українська",
    "ru": "Русский",
    "en": "English",
    "de": "Deutsch",
}

# Directives injected into Gemini system instructions to enforce output language
LANGUAGE_DIRECTIVES: Dict[str, str] = {
    "uk": "Ти ЗАВЖДИ формулюєш свої власні відповіді виключно українською мовою.",
    "ru": "Ты ВСЕГДА формулируешь свои собственные ответы исключительно на русском языке.",
    "en": "You ALWAYS formulate your own responses strictly in English.",
    "de": "Du formulierst deine eigenen Antworten IMMER ausschließlich auf Deutsch.",
}

# Static UI strings for commands, menus, and fallback error notifications
LOCALIZED_STRINGS: Dict[str, Dict[str, str]] = {
    "select_language_title": {
        "uk": "<b>Оберіть мову спілкування бота:</b>",
        "ru": "<b>Выберите язык общения бота:</b>",
        "en": "<b>Select language for the bot:</b>",
        "de": "<b>Sprache auswählen für den Bot:</b>",
    },
    "current_language_label": {
        "uk": "Поточна мова для цього чату",
        "ru": "Текущий язык для этого чата",
        "en": "Current language for this chat",
        "de": "Aktuelle Sprache für diesen Chat",
    },
    "language_selection_help": {
        "uk": "Ця мова застосовується для всіх відповідей бота у цьому чаті.",
        "ru": "Этот язык применяется для всех ответов бота в этом чате.",
        "en": "This language applies to all bot responses in this chat.",
        "de": "Diese Sprache gilt für alle Antworten des Bots in diesem Chat.",
    },
    "language_switched_success": {
        "uk": "Мову для цього чату успішно змінено на",
        "ru": "Язык для этого чата успешно изменен на",
        "en": "Language for this chat was successfully changed to",
        "de": "Die Sprache für diesen Chat wurde erfolgreich geändert auf",
    },
    "unknown_language": {
        "uk": "Невідома або непідтримувана мова.",
        "ru": "Неизвестный или неподдерживаемый язык.",
        "en": "Unknown or unsupported language.",
        "de": "Unbekannte oder nicht unterstützte Sprache.",
    },
    "api_error_message": {
        "uk": "Вибачте, сталася помилка під час обробки вашого запиту через штучний інтелект.",
        "ru": "Извините, произошла ошибка при обработке вашего запроса через искусственный интеллект.",
        "en": "Sorry, an error occurred while processing your request via artificial intelligence.",
        "de": "Entschuldigung, bei der Bearbeitung Ihrer Anfrage über KI ist ein Fehler aufgetreten.",
    },
    "ping_text": {
        "uk": "<b>Понг!</b> Бот активний і працює на Raspberry Pi.",
        "ru": "<b>Понг!</b> Бот активен и работает на Raspberry Pi.",
        "en": "<b>Pong!</b> Bot is active and running on Raspberry Pi.",
        "de": "<b>Pong!</b> Der Bot ist aktiv und läuft auf Raspberry Pi.",
    },
    "empty_tag_prompt": {
        "uk": (
            "<b>Привіт!</b> Чим я можу вам допомогти?\n"
            "Напишіть своє запитання або введіть <code>/help</code> для перегляду списку команд."
        ),
        "ru": (
            "<b>Привет!</b> Чем я могу вам помочь?\n"
            "Напишите свой вопрос или введите <code>/help</code> для просмотра списка команд."
        ),
        "en": (
            "<b>Hello!</b> How can I help you?\n"
            "Write your question or type <code>/help</code> to view the list of commands."
        ),
        "de": (
            "<b>Hallo!</b> Wie kann ich Ihnen helfen?\n"
            "Schreiben Sie Ihre Frage oder geben Sie <code>/help</code> ein, um die Befehlsliste anzuzeigen."
        ),
    },
    "no_target_roast_help": {
        "uk": (
            "<b>Кому саме влаштувати прожарку?</b> Будь ласка, вкажіть користувача через <code>@</code>, "
            "наприклад: <code>/roast @username</code>, або надішліть команду у відповідь (reply) на його повідомлення."
        ),
        "ru": (
            "<b>Кому именно устроить прожарку?</b> Пожалуйста, укажите пользователя через <code>@</code>, "
            "например: <code>/roast @username</code>, или отправьте команду в ответ (reply) на его сообщение."
        ),
        "en": (
            "<b>Who should be roasted?</b> Please specify a user via <code>@</code>, "
            "e.g.: <code>/roast @username</code>, or reply to their message."
        ),
        "de": (
            "<b>Wer soll geröstet werden?</b> Bitte geben Sie einen Benutzer über <code>@</code> an, "
            "z.B.: <code>/roast @username</code>, oder antworten Sie auf dessen Nachricht."
        ),
    },
    "no_prompt_meme_help": {
        "uk": (
            "<b>Вкажіть опис:</b> Будь ласка, вкажіть опис для генерації мему. Наприклад:\n"
            "<code>/meme кіт програміст лагодить сервер на Raspberry Pi</code>"
        ),
        "ru": (
            "<b>Укажите описание:</b> Пожалуйста, укажите описание для генерации мема. Например:\n"
            "<code>/meme кот программист чинит сервер на Raspberry Pi</code>"
        ),
        "en": (
            "<b>Provide a description:</b> Please provide a prompt for meme generation. For example:\n"
            "<code>/meme cat programmer fixing server on Raspberry Pi</code>"
        ),
        "de": (
            "<b>Beschreibung angeben:</b> Bitte geben Sie eine Beschreibung für das Meme an. Zum Beispiel:\n"
            "<code>/meme Katze Programmierer repariert Server auf Raspberry Pi</code>"
        ),
    },
    "start_text": {
        "uk": (
            "<b>Вітаю!</b> Я ваш Telegram-бот на базі Raspberry Pi.\n\n"
            "Я підтримую інтелектуальне спілкування за допомогою Google Gemini AI.\n"
            "У групах звертайтеся до мене через тег (наприклад, <code>@username</code>) або через відповідь (reply).\n"
            "Введіть <code>/help</code>, щоб переглянути список доступних команд."
        ),
        "ru": (
            "<b>Приветствую!</b> Я ваш Telegram-бот на базе Raspberry Pi.\n\n"
            "Я поддерживаю интеллектуальное общение с помощью Google Gemini AI.\n"
            "В группах обращайтесь ко мне через тег (например, <code>@username</code>) или через ответ (reply).\n"
            "Введите <code>/help</code>, чтобы просмотреть список доступных команд."
        ),
        "en": (
            "<b>Welcome!</b> I am your Telegram bot running on Raspberry Pi.\n\n"
            "I support smart conversation powered by Google Gemini AI.\n"
            "In groups, mention me via tag (e.g., <code>@username</code>) or by replying to my messages.\n"
            "Type <code>/help</code> to view the list of available commands."
        ),
        "de": (
            "<b>Willkommen!</b> Ich bin Ihr Telegram-Bot auf Basis von Raspberry Pi.\n\n"
            "Ich unterstütze intelligente Konversationen powered by Google Gemini AI.\n"
            "In Gruppen erwähnen Sie mich mit einem Tag (z. B. <code>@username</code>) oder per Antwort (reply).\n"
            "Geben Sie <code>/help</code> ein, um die Liste der verfügbaren Befehle anzuzeigen."
        ),
    },
    "public_help_text": {
        "uk": (
            "<b>Довідка щодо команд та можливостей бота:</b>\n\n"
            "<b>Основні команди:</b>\n"
            "• <code>/start</code> — Початок взаємодії та коротке привітання.\n"
            "• <code>/help</code> — Переглянути цей докладний довідник команд.\n"
            "• <code>/ping</code> — Перевірити доступність та час відповіді бота на Raspberry Pi.\n\n"
            "<b>Інтелектуальні функції (Gemini AI):</b>\n"
            "• <code>/news [тема]</code> — Свіжий дайджест актуальних новин із пошуком Google.\n"
            "  <i>Приклад:</i> <code>/news</code> (головні події) або <code>/news космос</code>.\n"
            "• <code>/roast [@користувач]</code> — Дружня стендап-прожарка учасника на основі його повідомлень.\n"
            "  <i>Використання:</i> вкажіть тег (<code>/roast @username</code>) або надішліть у відповідь на повідомлення.\n"
            "• <code>/meme [опис]</code> — Генерація зображення або мему через ШІ (Nano Banana).\n"
            "  <i>Приклад:</i> <code>/meme кіт програміст лагодить сервер</code>.\n"
            "• <code>/persona</code> — Обрати стиль/персону спілкування бота (стандартний або мем-лорд).\n"
            "• <code>/lang</code> — Обрати мову спілкування бота для цього чату (UA, RU, EN, DE).\n"
            "• <b>Спілкування з ШІ:</b>\n"
            "  В особистих чатах пишіть будь-що напряму, а в групах — згадуйте через тег або reply."
        ),
        "ru": (
            "<b>Справка по командам и возможностям бота:</b>\n\n"
            "<b>Основные команды:</b>\n"
            "• <code>/start</code> — Начало взаимодействия и краткое приветствие.\n"
            "• <code>/help</code> — Просмотреть этот справочник команд.\n"
            "• <code>/ping</code> — Проверить доступность и время ответа бота на Raspberry Pi.\n\n"
            "<b>Интеллектуальные функции (Gemini AI):</b>\n"
            "• <code>/news [тема]</code> — Свежий дайджест актуальных новостей с поиском Google.\n"
            "  <i>Пример:</i> <code>/news</code> (главные события) или <code>/news космос</code>.\n"
            "• <code>/roast [@пользователь]</code> — Дружеская стендап-прожарка участника на основе его сообщений.\n"
            "  <i>Использование:</i> укажите тег (<code>/roast @username</code>) или ответьте на сообщение.\n"
            "• <code>/meme [описание]</code> — Генерация изображения или мема через ИИ (Nano Banana).\n"
            "  <i>Пример:</i> <code>/meme кот программист чинит сервер</code>.\n"
            "• <code>/persona</code> — Выбрать стиль/персону общения бота (стандартный или мем-лорд).\n"
            "• <code>/lang</code> — Выбрать язык общения бота для этого чата (UA, RU, EN, DE).\n"
            "• <b>Общение с ИИ:</b>\n"
            "  В личных чатах пишите что угодно напрямую, а в группах — упоминайте через тег или reply."
        ),
        "en": (
            "<b>Bot commands and features directory:</b>\n\n"
            "<b>Core commands:</b>\n"
            "• <code>/start</code> — Start interaction and view greeting.\n"
            "• <code>/help</code> — View this command directory.\n"
            "• <code>/ping</code> — Check bot responsiveness and latency on Raspberry Pi.\n\n"
            "<b>AI Features (Gemini AI):</b>\n"
            "• <code>/news [topic]</code> — Fresh news briefing grounded with Google Search.\n"
            "  <i>Example:</i> <code>/news</code> (top headlines) or <code>/news tech</code>.\n"
            "• <code>/roast [@user]</code> — Friendly comedy roast of a member based on recent messages.\n"
            "  <i>Usage:</i> specify a tag (<code>/roast @username</code>) or reply to their message.\n"
            "• <code>/meme [prompt]</code> — Generate an AI image or meme (Nano Banana).\n"
            "  <i>Example:</i> <code>/meme cat programmer debugging server</code>.\n"
            "• <code>/persona</code> — Select bot personality style (standard or meme-lord).\n"
            "• <code>/lang</code> — Select bot communication language for this chat (UA, RU, EN, DE).\n"
            "• <b>Chatting with AI:</b>\n"
            "  In direct messages, send anything; in group chats, mention via @tag or reply."
        ),
        "de": (
            "<b>Befehlsübersicht und Bot-Funktionen:</b>\n\n"
            "<b>Grundlegende Befehle:</b>\n"
            "• <code>/start</code> — Interaktion starten und Begrüßung anzeigen.\n"
            "• <code>/help</code> — Diese Befehlsübersicht anzeigen.\n"
            "• <code>/ping</code> — Erreichbarkeit und Antwortzeit des Bots auf Raspberry Pi prüfen.\n\n"
            "<b>KI-Funktionen (Gemini AI):</b>\n"
            "• <code>/news [Thema]</code> — Aktueller Nachrichtendigest mit Google-Suche.\n"
            "  <i>Beispiel:</i> <code>/news</code> (Top-Meldungen) oder <code>/news Weltraum</code>.\n"
            "• <code>/roast [@Benutzer]</code> — Humorvoller Standup-Roast eines Mitglieds.\n"
            "  <i>Verwendung:</i> Tag angeben (<code>/roast @username</code>) oder auf Nachricht antworten.\n"
            "• <code>/meme [Beschreibung]</code> — KI-Bild oder Meme generieren (Nano Banana).\n"
            "  <i>Beispiel:</i> <code>/meme Katze Programmierer repariert Server</code>.\n"
            "• <code>/persona</code> — Persönlichkeitsstil des Bots wählen (Standard oder Meme-Lord).\n"
            "• <code>/lang</code> — Kommunikationssprache des Bots für diesen Chat wählen (UA, RU, EN, DE).\n"
            "• <b>Konversation mit KI:</b>\n"
            "  In Direktnachrichten einfach schreiben; in Gruppen per @Tag oder Antwort erwähnen."
        ),
    },
    "admin_help_text": {
        "uk": (
            "\n\n<b>Administration:</b>\n"
            "• <code>/access</code> — View approved access grants.\n"
            "• <code>/approve [id]</code> — Approve access for user or group.\n"
            "• <code>/reject [id]</code> — Revoke access for user or group.\n"
            "• <code>/stats</code> — Detailed Gemini token statistics and costs.\n"
            "• <code>/switch_reaction [id]</code> — Toggle AI emotional reactions for the chat."
        ),
        "ru": (
            "\n\n<b>Administration:</b>\n"
            "• <code>/access</code> — View approved access grants.\n"
            "• <code>/approve [id]</code> — Approve access for user or group.\n"
            "• <code>/reject [id]</code> — Revoke access for user or group.\n"
            "• <code>/stats</code> — Detailed Gemini token statistics and costs.\n"
            "• <code>/switch_reaction [id]</code> — Toggle AI emotional reactions for the chat."
        ),
        "en": (
            "\n\n<b>Administration:</b>\n"
            "• <code>/access</code> — View approved access grants.\n"
            "• <code>/approve [id]</code> — Approve access for user or group.\n"
            "• <code>/reject [id]</code> — Revoke access for user or group.\n"
            "• <code>/stats</code> — Detailed Gemini token statistics and costs.\n"
            "• <code>/switch_reaction [id]</code> — Toggle AI emotional reactions for the chat."
        ),
        "de": (
            "\n\n<b>Administration:</b>\n"
            "• <code>/access</code> — View approved access grants.\n"
            "• <code>/approve [id]</code> — Approve access for user or group.\n"
            "• <code>/reject [id]</code> — Revoke access for user or group.\n"
            "• <code>/stats</code> — Detailed Gemini token statistics and costs.\n"
            "• <code>/switch_reaction [id]</code> — Toggle AI emotional reactions for the chat."
        ),
    },
}


def is_supported_language(code: str) -> bool:
    """Validates if the given ISO language code is supported."""
    return code in SUPPORTED_LANGUAGES


def get_language_directive(code: str) -> str:
    """Returns the LLM language enforcement directive, defaulting to Ukrainian."""
    return LANGUAGE_DIRECTIVES.get(code, LANGUAGE_DIRECTIVES[DEFAULT_LANGUAGE])


def get_localized_string(key: str, lang_code: str) -> str:
    """Retrieves a static UI string, falling back to default language if missing."""
    key_dict = LOCALIZED_STRINGS.get(key, {})
    if lang_code in key_dict:
        return key_dict[lang_code]
    return key_dict.get(DEFAULT_LANGUAGE, key)
