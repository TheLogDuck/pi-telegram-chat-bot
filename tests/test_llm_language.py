# Unit tests for multi-language support in Gemini conversational generation.
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from core.llm.chat import generate_response
from core.llm.config import DEFAULT_SYSTEM_INSTRUCTION


def test_generate_response_default_language_keeps_default_instruction() -> None:
    """Verifies that with no language specified, the default system instruction is preserved."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Тестова відповідь"
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    text, model = asyncio.run(
        generate_response(
            prompt="Привіт",
            client=mock_client,
        )
    )

    assert text == "Тестова відповідь"
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert call_kwargs["config"].system_instruction == DEFAULT_SYSTEM_INSTRUCTION


def test_generate_response_with_russian_language() -> None:
    """Verifies that language='ru' instructs the model to reply in Russian."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Привет! Я бот."
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    text, model = asyncio.run(
        generate_response(
            prompt="Привет",
            client=mock_client,
            language="ru",
        )
    )

    assert text == "Привет! Я бот."
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    instruction = call_kwargs["config"].system_instruction
    assert "на русском языке" in instruction
    # Ensure no contradictory Ukrainian-only directive remains
    assert "виключно українською мовою" not in instruction


def test_generate_response_with_english_language() -> None:
    """Verifies that language='en' instructs the model to reply in English."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hello! How can I help?"
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    text, model = asyncio.run(
        generate_response(
            prompt="Hello",
            client=mock_client,
            language="en",
        )
    )

    assert text == "Hello! How can I help?"
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    instruction = call_kwargs["config"].system_instruction
    assert "in English" in instruction


def test_generate_response_with_german_language() -> None:
    """Verifies that language='de' instructs the model to reply in German."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hallo! Wie kann ich helfen?"
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    text, model = asyncio.run(
        generate_response(
            prompt="Hallo",
            client=mock_client,
            language="de",
        )
    )

    assert text == "Hallo! Wie kann ich helfen?"
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    instruction = call_kwargs["config"].system_instruction
    assert "auf Deutsch" in instruction


def test_generate_news_briefing_with_russian_language() -> None:
    """Verifies that generate_news_briefing requests Russian output when language='ru'."""
    from core.llm.news import generate_news_briefing

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "1. Главные мировые новости..."
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    text, model = asyncio.run(
        generate_news_briefing(
            topic="технологии",
            client=mock_client,
            language="ru",
        )
    )

    assert text == "1. Главные мировые новости..."
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert "Подготовь краткий информационный дайджест" in call_kwargs["contents"]
    assert "на русском языке" in call_kwargs["config"].system_instruction

