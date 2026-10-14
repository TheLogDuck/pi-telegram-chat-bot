# Unit tests for modules/intent.py.
# Validates trilingual keyword matching, typo tolerance, argument extraction, and fallback.
import pytest
from modules.intent import (
    IntentResult,
    IntentType,
    detect_intent,
    extract_news_topic,
    extract_target_user,
)


def test_detect_intent_slash_commands() -> None:
    """Verifies that standard slash commands are detected with 100% confidence."""
    res_roast = detect_intent("/roast @alex")
    assert res_roast.intent == IntentType.ROAST
    assert res_roast.target_user == "@alex"

    res_news = detect_intent("/news technology")
    assert res_news.intent == IntentType.NEWS
    assert res_news.topic == "technology"

    res_ping = detect_intent("/ping")
    assert res_ping.intent == IntentType.PING

    res_help = detect_intent("/help")
    assert res_help.intent == IntentType.HELP

    res_stats = detect_intent("/stats")
    assert res_stats.intent == IntentType.STATS

    res_meme = detect_intent("/meme funny duck")
    assert res_meme.intent == IntentType.MEME
    assert res_meme.topic == "funny duck"


def test_detect_intent_ukrainian_triggers() -> None:
    """Verifies Ukrainian natural language commands and argument extraction."""
    res_roast1 = detect_intent("просмаж @taras")
    assert res_roast1.intent == IntentType.ROAST
    assert res_roast1.target_user == "@taras"

    res_roast2 = detect_intent("просмажити олега")
    assert res_roast2.intent == IntentType.ROAST
    assert res_roast2.target_user == "@олега"

    res_news = detect_intent("останні новини про космос")
    assert res_news.intent == IntentType.NEWS
    assert res_news.topic == "космос"

    res_meme = detect_intent("мем про кота програміста")
    assert res_meme.intent == IntentType.MEME
    assert res_meme.topic == "кота програміста"

    res_ping = detect_intent("пінг")
    assert res_ping.intent == IntentType.PING

    res_help = detect_intent("допомога")
    assert res_help.intent == IntentType.HELP

    res_stats = detect_intent("статистика")
    assert res_stats.intent == IntentType.STATS


def test_detect_intent_russian_triggers() -> None:
    """Verifies Russian natural language commands and argument extraction."""
    res_roast = detect_intent("зароасти @ivan")
    assert res_roast.intent == IntentType.ROAST
    assert res_roast.target_user == "@ivan"

    res_prozhar = detect_intent("прожарь @ivan")
    assert res_prozhar.intent == IntentType.ROAST
    assert res_prozhar.target_user == "@ivan"

    res_news = detect_intent("новости про науку")
    assert res_news.intent == IntentType.NEWS
    assert res_news.topic == "науку"

    res_ping = detect_intent("пинг")
    assert res_ping.intent == IntentType.PING

    res_help = detect_intent("помощь")
    assert res_help.intent == IntentType.HELP

    res_stats = detect_intent("статы")
    assert res_stats.intent == IntentType.STATS


def test_detect_intent_english_triggers() -> None:
    """Verifies English natural language commands and argument extraction."""
    res_roast = detect_intent("roast @john")
    assert res_roast.intent == IntentType.ROAST
    assert res_roast.target_user == "@john"

    res_news = detect_intent("news about artificial intelligence")
    assert res_news.intent == IntentType.NEWS
    assert res_news.topic == "artificial intelligence"

    res_ping = detect_intent("ping")
    assert res_ping.intent == IntentType.PING

    res_help = detect_intent("help")
    assert res_help.intent == IntentType.HELP

    res_stats = detect_intent("stats")
    assert res_stats.intent == IntentType.STATS


def test_detect_intent_fuzzy_typos() -> None:
    """Verifies that fuzzy matching with difflib catches common spelling typos."""
    # Typo: просмаш instead of просмаж
    res_typo1 = detect_intent("просмаш @serhiy")
    assert res_typo1.intent == IntentType.ROAST
    assert res_typo1.target_user == "@serhiy"

    # Typo: зарости instead of зароасти
    res_typo2 = detect_intent("зарости @serhiy")
    assert res_typo2.intent == IntentType.ROAST
    assert res_typo2.target_user == "@serhiy"

    # Typo / synonym: новинки instead of новини
    res_typo3 = detect_intent("новинки кіно")
    assert res_typo3.intent == IntentType.NEWS


def test_detect_intent_fallback_to_chat() -> None:
    """Verifies that queries without command intents fall back to CHAT."""
    res1 = detect_intent("розкажи мені про історію Києва")
    assert res1.intent == IntentType.CHAT

    res2 = detect_intent("какая сегодня погода?")
    assert res2.intent == IntentType.CHAT

    res3 = detect_intent("how does gravity work?")
    assert res3.intent == IntentType.CHAT

    res_empty = detect_intent("   ")
    assert res_empty.intent == IntentType.CHAT


def test_detect_intent_german_and_english_roast() -> None:
    """Verifies English and German roast triggers, slang, and target extraction."""
    # English: roast with target
    res_en1 = detect_intent("roast @john")
    assert res_en1.intent == IntentType.ROAST
    assert res_en1.target_user == "@john"

    # English: burn slang
    res_en2 = detect_intent("burn @developer")
    assert res_en2.intent == IntentType.ROAST
    assert res_en2.target_user == "@developer"

    # English: diss slang
    res_en3 = detect_intent("diss @sam")
    assert res_en3.intent == IntentType.ROAST
    assert res_en3.target_user == "@sam"

    # English: self-referential roast me
    res_en4 = detect_intent("roast me please")
    assert res_en4.intent == IntentType.ROAST
    assert res_en4.target_user == "@me"

    # German: roaste with target
    res_de1 = detect_intent("roaste @klaus")
    assert res_de1.intent == IntentType.ROAST
    assert res_de1.target_user == "@klaus"

    # German: zerlege slang
    res_de2 = detect_intent("zerlege @klaus")
    assert res_de2.intent == IntentType.ROAST
    assert res_de2.target_user == "@klaus"

    # German: verspotten with preposition skip
    res_de3 = detect_intent("verspotte über @klaus")
    assert res_de3.intent == IntentType.ROAST
    assert res_de3.target_user == "@klaus"


def test_detect_intent_german_and_english_meme() -> None:
    """Verifies English and German meme creation triggers and prompt cleaning."""
    # German: generiere einen meme über katze
    res_de1 = detect_intent("generiere einen meme über katze")
    assert res_de1.intent == IntentType.MEME
    assert res_de1.topic == "katze"

    # German: zeichne ein bild von weltall
    res_de2 = detect_intent("zeichne ein bild von weltall")
    assert res_de2.intent == IntentType.MEME
    assert res_de2.topic == "weltall"

    # English: make a meme about funny cats
    res_en1 = detect_intent("make a meme about funny cats")
    assert res_en1.intent == IntentType.MEME
    assert res_en1.topic == "funny cats"

    # English: draw a picture of a rocket
    res_en2 = detect_intent("draw a picture of rocket")
    assert res_en2.intent == IntentType.MEME
    assert res_en2.topic == "rocket"


def test_detect_intent_slang_ukrainian_and_russian() -> None:
    """Verifies Ukrainian and Russian slang triggers for roast and meme intents."""
    # Ukrainian roast: рознеси
    res_roast_uk = detect_intent("рознеси @taras")
    assert res_roast_uk.intent == IntentType.ROAST
    assert res_roast_uk.target_user == "@taras"

    # Ukrainian roast: постібися над @user
    res_roast_uk2 = detect_intent("постібися над @taras")
    assert res_roast_uk2.intent == IntentType.ROAST
    assert res_roast_uk2.target_user == "@taras"

    # Russian roast: постебись над @ivan
    res_roast_ru = detect_intent("постебись над @ivan")
    assert res_roast_ru.intent == IntentType.ROAST
    assert res_roast_ru.target_user == "@ivan"

    # Ukrainian meme: намалюй кота в капелюсі
    res_meme_uk = detect_intent("намалюй кота в капелюсі")
    assert res_meme_uk.intent == IntentType.MEME
    assert res_meme_uk.topic == "кота в капелюсі"

    # Ukrainian meme: запили пікчу про програміста
    res_meme_uk2 = detect_intent("запили пікчу про програміста")
    assert res_meme_uk2.intent == IntentType.MEME
    assert res_meme_uk2.topic == "програміста"

    # Russian meme: нарисуй собаку на скейте
    res_meme_ru = detect_intent("нарисуй собаку на скейте")
    assert res_meme_ru.intent == IntentType.MEME
    assert res_meme_ru.topic == "собаку на скейте"

    # Russian meme: сделай фотожабу про дедлайн
    res_meme_ru2 = detect_intent("сделай фотожабу про дедлайн")
    assert res_meme_ru2.intent == IntentType.MEME
    assert res_meme_ru2.topic == "дедлайн"