# Unit tests for core/llm.py.
# All tests mock the google-genai client to ensure 100% offline execution without network or tokens.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.llm import (
    API_ERROR_MESSAGE,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_INSTRUCTION,
    generate_response,
    get_gemini_client,
)


def test_get_gemini_client_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies client creation when GEMINI_API_KEY is defined."""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-test-key-12345")

    client = get_gemini_client()
    assert client is not None


def test_get_gemini_client_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that a ValueError is raised if GEMINI_API_KEY is absent."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is missing"):
        get_gemini_client()


def test_generate_response_empty_prompt() -> None:
    """Verifies that an empty prompt immediately returns guidance without hitting the API."""
    mock_client = MagicMock()
    result = asyncio.run(generate_response("   ", client=mock_client))

    assert "Будь ласка, вкажіть повідомлення" in result
    mock_client.aio.models.generate_content.assert_not_called()


def test_generate_response_success() -> None:
    """Verifies successful non-blocking text generation using mocked client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Привіт! Я готовий допомогти вам."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result = asyncio.run(
        generate_response("Привіт, як справи?", client=mock_client)
    )

    assert result == "Привіт! Я готовий допомогти вам."
    mock_client.aio.models.generate_content.assert_awaited_once()

    # Check arguments passed to generate_content
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert call_kwargs["model"] == DEFAULT_MODEL
    assert call_kwargs["contents"] == "Привіт, як справи?"
    assert call_kwargs["config"].system_instruction == DEFAULT_SYSTEM_INSTRUCTION


def test_generate_response_custom_system_instruction() -> None:
    """Verifies that custom system instructions can be supplied."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Спеціальна відповідь."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    custom_instruction = "Спеціальна інструкція."
    result = asyncio.run(
        generate_response(
            "Тестове запитання",
            system_instruction=custom_instruction,
            client=mock_client,
        )
    )

    assert result == "Спеціальна відповідь."
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert call_kwargs["config"].system_instruction == custom_instruction


def test_generate_response_handles_api_exception() -> None:
    """Verifies that exceptions during API calls are caught and return a safe message."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Simulated network timeout")
    )

    result = asyncio.run(
        generate_response("Будь-який запит", client=mock_client)
    )

    assert result == API_ERROR_MESSAGE


def test_generate_response_handles_empty_api_text() -> None:
    """Verifies fallback when Gemini returns None or an empty text field."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result = asyncio.run(
        generate_response("Будь-який запит", client=mock_client)
    )

    assert result == API_ERROR_MESSAGE
