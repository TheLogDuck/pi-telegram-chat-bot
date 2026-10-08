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
    result, model = asyncio.run(generate_response("   ", client=mock_client))

    assert "Будь ласка, вкажіть повідомлення" in result
    assert model is None
    mock_client.aio.models.generate_content.assert_not_called()


def test_generate_response_success() -> None:
    """Verifies successful non-blocking text generation using mocked client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Привіт! Я готовий допомогти вам."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result, model = asyncio.run(
        generate_response("Привіт, як справи?", client=mock_client)
    )

    assert result == "Привіт! Я готовий допомогти вам."
    assert model == DEFAULT_MODEL
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
    result, model = asyncio.run(
        generate_response(
            "Тестове запитання",
            system_instruction=custom_instruction,
            client=mock_client,
        )
    )

    assert result == "Спеціальна відповідь."
    assert model == DEFAULT_MODEL
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert call_kwargs["config"].system_instruction == custom_instruction


def test_generate_response_handles_api_exception() -> None:
    """Verifies that exceptions during API calls are caught and return a safe message."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Simulated network timeout")
    )

    result, model = asyncio.run(
        generate_response("Будь-який запит", client=mock_client)
    )

    assert result == API_ERROR_MESSAGE
    assert model is None


def test_generate_response_handles_empty_api_text() -> None:
    """Verifies fallback when Gemini returns None or an empty text field."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result, model = asyncio.run(
        generate_response("Будь-який запит", client=mock_client)
    )
    assert result == API_ERROR_MESSAGE
    assert model is None


def test_generate_news_briefing_with_topic() -> None:
    """Verifies that news briefing includes the topic and Google Search tool."""
    from core.llm import NEWS_SYSTEM_INSTRUCTION, generate_news_briefing

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "1. Новини науки сьогодні..."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result, model = asyncio.run(generate_news_briefing("наука", client=mock_client))

    assert result == "1. Новини науки сьогодні..."
    assert model == DEFAULT_MODEL
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert "наука" in call_kwargs["contents"]
    assert call_kwargs["config"].system_instruction == NEWS_SYSTEM_INSTRUCTION
    # Verify Google Search grounding tool was attached
    assert call_kwargs["config"].tools is not None
    assert len(call_kwargs["config"].tools) == 1
    assert call_kwargs["config"].tools[0].google_search is not None


def test_generate_news_briefing_default_headlines() -> None:
    """Verifies that news briefing without topic requests top headlines."""
    from core.llm import generate_news_briefing

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "1. Головні світові новини..."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result, model = asyncio.run(generate_news_briefing(None, client=mock_client))

    assert result == "1. Головні світові новини..."
    assert model == DEFAULT_MODEL
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert "головних світових" in call_kwargs["contents"]


def test_generate_news_briefing_handles_exception() -> None:
    """Verifies exception handling in news briefing returns API_ERROR_MESSAGE."""
    from core.llm import generate_news_briefing

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Google search grounding unavailable")
    )

    result, model = asyncio.run(generate_news_briefing("технології", client=mock_client))
    assert result == API_ERROR_MESSAGE
    assert model is None


def test_generate_roast_with_context() -> None:
    """Verifies that generate_roast formats target and context quotes in prompt."""
    from core.llm import generate_roast

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Смішний роаст про кодування ночами!"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    context_msgs = ["я пишу код о 3 ночі", "знову баг у продакшені"]
    result, model = asyncio.run(generate_roast("@developer", context_messages=context_msgs, client=mock_client))

    assert result == "Смішний роаст про кодування ночами!"
    assert model == DEFAULT_MODEL
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert "@developer" in call_kwargs["contents"]
    assert "я пишу код о 3 ночі" in call_kwargs["contents"]


def test_generate_roast_without_context() -> None:
    """Verifies that generate_roast generates generic roast when no messages exist."""
    from core.llm import generate_roast

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Роаст користувача, який мовчить у засідці!"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result, model = asyncio.run(generate_roast("lurker", context_messages=None, client=mock_client))

    assert result == "Роаст користувача, який мовчить у засідці!"
    assert model == DEFAULT_MODEL
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert "@lurker" in call_kwargs["contents"]
    assert "засідці" in call_kwargs["contents"]


def test_generate_roast_handles_failure() -> None:
    """Verifies that generate_roast returns API_ERROR_MESSAGE when all models fail."""
    from core.llm import generate_roast

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Quota limit reached")
    )

    result, model = asyncio.run(generate_roast("alice", client=mock_client))
    assert result == API_ERROR_MESSAGE
    assert model is None


def test_record_usage_calculates_cost() -> None:
    """Verifies that record_usage parses usage_metadata and calculates USD cost."""
    from core.llm import record_usage

    mock_response = MagicMock()
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 1000
    mock_usage.candidates_token_count = 500
    mock_usage.total_token_count = 1500
    mock_response.usage_metadata = mock_usage

    with patch("core.db.async_save_token_usage", new_callable=AsyncMock) as mock_save:
        asyncio.run(
            record_usage(
                response=mock_response,
                model_name="gemini-3.8-flash",
                feature="chat",
                chat_id=123,
                user_id=456,
            )
        )
        mock_save.assert_awaited_once()
        call_kwargs = mock_save.await_args.kwargs
        assert call_kwargs["model"] == "gemini-3.8-flash"
        assert call_kwargs["feature"] == "chat"
        assert call_kwargs["prompt_tokens"] == 1000
        assert call_kwargs["completion_tokens"] == 500
        assert call_kwargs["total_tokens"] == 1500
        # 1000 * 0.10/1M + 500 * 0.40/1M = 0.0001 + 0.0002 = 0.0003
        assert abs(call_kwargs["cost_usd"] - 0.0003) < 1e-6


def test_generate_meme_image_success() -> None:
    """Verifies that generate_meme_image extracts image bytes and records usage."""
    from core.llm import DEFAULT_IMAGE_MODEL, generate_meme_image

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"fake-png-bytes"
    mock_part.inline_data.mime_type = "image/png"
    mock_candidate.content.parts = [mock_part]
    mock_response.candidates = [mock_candidate]
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    img_bytes, mime_type, err, model = asyncio.run(
        generate_meme_image("кіт на даху", client=mock_client)
    )

    assert img_bytes == b"fake-png-bytes"
    assert mime_type == "image/png"
    assert err is None
    assert model == DEFAULT_IMAGE_MODEL
    mock_client.aio.models.generate_content.assert_awaited_once()
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert call_kwargs["model"] == DEFAULT_IMAGE_MODEL
    assert "кіт на даху" in call_kwargs["contents"]


def test_generate_meme_image_empty_prompt() -> None:
    """Verifies that empty prompt returns guidance without hitting API."""
    from core.llm import generate_meme_image

    mock_client = MagicMock()
    img_bytes, mime_type, err, model = asyncio.run(
        generate_meme_image("   ", client=mock_client)
    )

    assert img_bytes is None
    assert "вкажіть опис" in err
    assert model is None
    mock_client.aio.models.generate_content.assert_not_called()


