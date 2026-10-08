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


def test_detect_intent_image_slang_ukrainian_and_russian() -> None:
    """Verifies that Ukrainian and Russian slang and drawing verbs trigger MEME intent."""
    # Ukrainian: намалюй
    res1 = detect_intent("намалюй кота в капелюсі")
    assert res1.intent == IntentType.MEME
    assert res1.topic == "кота в капелюсі"

    # Ukrainian: запили пікчу
    res2 = detect_intent("запили пікчу про програміста")
    assert res2.intent == IntentType.MEME
    assert res2.topic == "програміста"

    # Ukrainian: збацай мемас
    res3 = detect_intent("збацай мемас як кіт ламає прод")
    assert res3.intent == IntentType.MEME
    assert res3.topic == "кіт ламає прод"

    # Russian: нарисуй
    res4 = detect_intent("нарисуй собаку на скейте")
    assert res4.intent == IntentType.MEME
    assert res4.topic == "собаку на скейте"

    # Russian: сделай фотожабу
    res5 = detect_intent("сделай фотожабу про дедлайн")
    assert res5.intent == IntentType.MEME
    assert res5.topic == "дедлайн"

    # Russian: пикча
    res6 = detect_intent("пикча космического корабля")
    assert res6.intent == IntentType.MEME
    assert res6.topic == "космического корабля"

    # Ukrainian: згенеруй картинку
    res7 = detect_intent("згенеруй картинку захід сонця")
    assert res7.intent == IntentType.MEME
    assert res7.topic == "захід сонця"


def test_detect_intent_roast_slang_ukrainian_and_russian() -> None:
    """Verifies colloquial Ukrainian and Russian roast slang and target extraction."""
    # Ukrainian: рознеси
    res1 = detect_intent("рознеси @taras")
    assert res1.intent == IntentType.ROAST
    assert res1.target_user == "@taras"

    # Ukrainian: постібися над @user (skips preposition 'над')
    res2 = detect_intent("постібися над @taras")
    assert res2.intent == IntentType.ROAST
    assert res2.target_user == "@taras"

    # Ukrainian: підколи олега
    res3 = detect_intent("підколи олега")
    assert res3.intent == IntentType.ROAST
    assert res3.target_user == "@олега"

    # Russian: постебись над @ivan
    res4 = detect_intent("постебись над @ivan")
    assert res4.intent == IntentType.ROAST
    assert res4.target_user == "@ivan"

    # Russian: затролль
    res5 = detect_intent("затролль @ivan")
    assert res5.intent == IntentType.ROAST
    assert res5.target_user == "@ivan"


