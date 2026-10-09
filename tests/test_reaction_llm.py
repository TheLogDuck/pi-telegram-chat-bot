# Unit tests for LLM reaction decision engine in core/llm.py.
# Fully mocks google-genai to ensure zero network traffic and zero token costs.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.llm import (
    ALLOWED_TELEGRAM_REACTIONS,
    DEFAULT_REACTION_MODEL,
    decide_message_reaction,
    get_candidate_reaction_models,
)


def test_allowed_telegram_reactions_contains_standard_emojis() -> None:
    """Verifies that the whitelist contains common Telegram reactions."""
    assert "👍" in ALLOWED_TELEGRAM_REACTIONS
    assert "🔥" in ALLOWED_TELEGRAM_REACTIONS
    assert "🤡" in ALLOWED_TELEGRAM_REACTIONS
    assert "🗿" in ALLOWED_TELEGRAM_REACTIONS
    assert "NONE" not in ALLOWED_TELEGRAM_REACTIONS


def test_get_candidate_reaction_models_default_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies candidate reaction models start with the cheapest Flash-Lite tier."""
    monkeypatch.delenv("GEMINI_REACTION_MODEL", raising=False)
    candidates = get_candidate_reaction_models()
    assert candidates[0] == DEFAULT_REACTION_MODEL
    assert "gemini-3.5-flash-lite" in candidates


    # Configured override
    monkeypatch.setenv("GEMINI_REACTION_MODEL", "custom-lite-model")
    custom_candidates = get_candidate_reaction_models()
    assert custom_candidates[0] == "custom-lite-model"


def test_decide_reaction_valid_emoji() -> None:
    """Verifies successful reaction decision returning a valid whitelisted emoji."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "🔥"
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    history = [
        {"username": "alex", "text": "We just shipped the update!"},
        {"username": "dmitry", "text": "All tests are passing."},
    ]

    emoji, model = asyncio.run(
        decide_message_reaction(
            current_message="Servers are running smoothly!",
            chat_history=history,
            persona_key="standard",
            author_name="alex",
            client=mock_client,
        )
    )

    assert emoji == "🔥"
    assert model == DEFAULT_REACTION_MODEL
    mock_client.aio.models.generate_content.assert_awaited_once()

    # Check contents passed to the LLM
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    prompt = call_kwargs["contents"]
    assert "alex: We just shipped the update!" in prompt
    assert "Servers are running smoothly!" in prompt


def test_decide_reaction_model_returns_none() -> None:
    """Verifies that if the LLM decides no reaction is warranted, None is returned."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "NONE"
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    emoji, model = asyncio.run(
        decide_message_reaction(
            current_message="Ok",
            chat_history=[],
            persona_key="standard",
            client=mock_client,
        )
    )

    assert emoji is None
    assert model == DEFAULT_REACTION_MODEL


def test_decide_reaction_invalid_or_wordy_output_filtered() -> None:
    """Verifies that chatter or non-whitelisted characters from the LLM are safely discarded."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "I think you should use a smiley face here because it is nice."
    mock_response.usage_metadata = None
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    emoji, model = asyncio.run(
        decide_message_reaction(
            current_message="Random text",
            chat_history=[],
            persona_key="cynic",
            client=mock_client,
        )
    )

    # Disallowed text must result in None to protect against Telegram API errors
    assert emoji is None
    assert model == DEFAULT_REACTION_MODEL


def test_decide_reaction_model_failover() -> None:
    """Verifies failover to next model candidate if first model raises an exception."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "👍"
    mock_response.usage_metadata = None

    # First model call fails, second model call succeeds
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=[RuntimeError("429 Resource Exhausted"), mock_response]
    )

    emoji, model = asyncio.run(
        decide_message_reaction(
            current_message="Great job",
            chat_history=[],
            persona_key="standard",
            client=mock_client,
        )
    )

    assert emoji == "👍"
    assert mock_client.aio.models.generate_content.await_count == 2


@patch("core.llm.record_usage", new_callable=AsyncMock)
def test_decide_reaction_records_usage(mock_record_usage: AsyncMock) -> None:
    """Verifies telemetry logs token usage with feature='reaction'."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "🎉"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    emoji, model = asyncio.run(
        decide_message_reaction(
            current_message="Happy birthday!",
            chat_history=[],
            persona_key="standard",
            chat_id=-1001,
            user_id=2001,
            client=mock_client,
        )
    )

    assert emoji == "🎉"
    mock_record_usage.assert_awaited_once_with(
        mock_response,
        DEFAULT_REACTION_MODEL,
        "reaction",
        -1001,
        2001,
    )
