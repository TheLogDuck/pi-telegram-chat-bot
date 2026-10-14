# Unit tests for language registry, directives, and UI localization.
import pytest
from core.languages import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_language_directive,
    get_localized_string,
    is_supported_language,
)


def test_supported_languages_contains_four_core_languages() -> None:
    """Verifies that Ukrainian, Russian, English, and German are all registered."""
    expected_codes = {"uk", "ru", "en", "de"}
    assert expected_codes.issubset(set(SUPPORTED_LANGUAGES.keys()))
    assert DEFAULT_LANGUAGE == "uk"


def test_is_supported_language() -> None:
    """Verifies validation helper for language codes."""
    assert is_supported_language("uk") is True
    assert is_supported_language("ru") is True
    assert is_supported_language("en") is True
    assert is_supported_language("de") is True
    assert is_supported_language("es") is False
    assert is_supported_language("unknown") is False


def test_get_language_directive() -> None:
    """Verifies that each language returns an explicit formulation directive for LLMs."""
    ua_directive = get_language_directive("uk")
    ru_directive = get_language_directive("ru")
    en_directive = get_language_directive("en")
    de_directive = get_language_directive("de")

    assert "українською мовою" in ua_directive
    assert "на русском языке" in ru_directive
    assert "in English" in en_directive
    assert "auf Deutsch" in de_directive

    # Fallback to default language (uk) if unknown code is provided
    fallback_directive = get_language_directive("fr")
    assert "українською мовою" in fallback_directive


def test_get_localized_string() -> None:
    """Verifies that static UI strings are returned in the requested language."""
    # Test valid key in all supported languages
    assert "Оберіть мову" in get_localized_string("select_language_title", "uk")
    assert "Выберите язык" in get_localized_string("select_language_title", "ru")
    assert "Select language" in get_localized_string("select_language_title", "en")
    assert "Sprache auswählen" in get_localized_string("select_language_title", "de")

    # Fallback to default language if requested language is unsupported
    assert "Оберіть мову" in get_localized_string("select_language_title", "unknown_lang")
