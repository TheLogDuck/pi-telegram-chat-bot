# Unit tests for persona module and persona-based LLM generation.
# Completely offline execution using mocks and in-memory SQLite databases.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Update
from telegram.constants import ParseMode

from core.database.connection import init_db
from core.database.personas import (
    async_get_user_persona,
    async_set_user_persona,
    get_user_persona,
    set_user_persona,
)
from core.llm import generate_meme_image, generate_response, generate_roast
from core.personas import (
    STANDARD_PERSONA,
    get_persona,
)
from modules.intent import IntentType, detect_intent
from modules.persona import (
    CALLBACK_PREFIX,
    build_persona_keyboard,
    format_persona_selection_text,
    persona_callback_query,
    persona_command,
)


def test_get_persona_fallbacks() -> None:
    """Verifies that get_persona resolves valid keys and safely falls back to standard."""
    assert get_persona("standard").key == "standard"
    assert get_persona("meme_lord").key == "meme_lord"
    assert get_persona("cynic").key == "standard"
    assert get_persona(None).key == "standard"
    assert get_persona("nonexistent_alien_persona").key == "standard"


def test_db_user_persona_isolation(tmp_path) -> None:
    """Verifies that persona preferences are persisted per user and isolated."""
    db_file = str(tmp_path / "test_persona.db")
    init_db(db_file)

    # Initial query for unconfigured user defaults to standard
    assert get_user_persona(1001, db_path=db_file) == "standard"
    assert get_user_persona(1002, db_path=db_file) == "standard"

    # Set user 1001 to meme_lord
    set_user_persona(1001, "meme_lord", db_path=db_file)
    assert get_user_persona(1001, db_path=db_file) == "meme_lord"
    # User 1002 remains unaffected
    assert get_user_persona(1002, db_path=db_file) == "standard"

    # Async getters and setters verification
    asyncio.run(async_set_user_persona(1002, "meme_lord", db_path=db_file))
    assert asyncio.run(async_get_user_persona(1002, db_path=db_file)) == "meme_lord"


def test_build_persona_keyboard() -> None:
    """Verifies keyboard buttons format and marks active persona."""
    markup = build_persona_keyboard("standard")
    buttons = [row[0] for row in markup.inline_keyboard]
    assert len(buttons) == 2

    # Standard should be marked as active
    assert "[Обрано]" in buttons[0].text
    assert buttons[0].callback_data == f"{CALLBACK_PREFIX}standard"

    # Meme Lord should not be marked active
    assert "[Обрано]" not in buttons[1].text
    assert buttons[1].callback_data == f"{CALLBACK_PREFIX}meme_lord"


def test_persona_command_no_args_displays_keyboard(tmp_path) -> None:
    """Verifies /persona without arguments displays selection message with buttons."""
    db_file = str(tmp_path / "test_persona_cmd.db")
    init_db(db_file)

    update = MagicMock(spec=Update)
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.effective_message = message
    update.effective_user.id = 5001

    context = MagicMock()
    context.args = []

    with patch("modules.persona.async_get_user_persona", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = "standard"
        asyncio.run(persona_command(update, context))

        message.reply_text.assert_awaited_once()
        call_kwargs = message.reply_text.await_args.kwargs
        assert "Вибір стилю спілкування бота:" in message.reply_text.await_args.args[0]
        assert call_kwargs["reply_markup"] is not None
        assert call_kwargs["parse_mode"] == ParseMode.HTML


def test_persona_command_with_arg_shortcut() -> None:
    """Verifies /persona standard sets the persona directly without showing buttons."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.effective_message = message
    update.effective_user.id = 5002

    context = MagicMock()
    context.args = ["standard"]

    with patch("modules.persona.async_set_user_persona", new_callable=AsyncMock) as mock_set:
        asyncio.run(persona_command(update, context))

        mock_set.assert_awaited_once_with(5002, "standard")
        message.reply_text.assert_awaited_once()
        text = message.reply_text.await_args.args[0]
        assert "Стиль успішно змінено:" in text
        assert "Стандартний" in text


def test_persona_callback_query_updates_choice() -> None:
    """Verifies clicking an inline button updates the persona and edits the UI."""
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = f"{CALLBACK_PREFIX}meme_lord"
    query.from_user.id = 7001
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    update.effective_user.id = 7001

    context = MagicMock()

    with patch("modules.persona.async_set_user_persona", new_callable=AsyncMock) as mock_set:
        asyncio.run(persona_callback_query(update, context))

        mock_set.assert_awaited_once_with(7001, "meme_lord")
        query.answer.assert_awaited_once_with("Обрано: Мем-лорд")
        query.edit_message_text.assert_awaited_once()
        edit_kwargs = query.edit_message_text.await_args.kwargs
        assert "Мем-лорд" in edit_kwargs["text"]
        assert edit_kwargs["reply_markup"] is not None


def test_persona_intent_detection() -> None:
    """Verifies natural language intent detection for persona command."""
    res = detect_intent("/persona")
    assert res.intent == IntentType.PERSONA

    res2 = detect_intent("персона")
    assert res2.intent == IntentType.PERSONA


def test_persona_command_with_meme_lord_shortcut() -> None:
    """Verifies /persona meme_lord sets the persona directly."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.effective_message = message
    update.effective_user.id = 5003

    context = MagicMock()
    context.args = ["meme_lord"]

    with patch("modules.persona.async_set_user_persona", new_callable=AsyncMock) as mock_set:
        asyncio.run(persona_command(update, context))

        mock_set.assert_awaited_once_with(5003, "meme_lord")
        message.reply_text.assert_awaited_once()
        text = message.reply_text.await_args.args[0]
        assert "Стиль успішно змінено:" in text
        assert "Мем-лорд" in text


def test_llm_generate_roast_with_meme_lord_persona() -> None:
    """Verifies that generate_roast applies meme-lord shitpost/irony prompt."""
    from core.personas import MEME_LORD_PERSONA

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Базова просмажка від мем-лорда."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result, model = asyncio.run(
        generate_roast(
            target_name="victim_user",
            context_messages=["я роблю дизайн у ворді"],
            persona_key="meme_lord",
            client=mock_client,
        )
    )

    assert result == "Базова просмажка від мем-лорда."
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    config = call_kwargs["config"]
    assert config.system_instruction == MEME_LORD_PERSONA.roast_system_instruction
    assert "постіронічну просмажку" in call_kwargs["contents"]


def test_llm_generate_meme_with_meme_lord_persona() -> None:
    """Verifies that generate_meme_image applies viral meme prompt template."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"viral_meme_bytes"
    mock_part.inline_data.mime_type = "image/png"
    mock_candidate.content.parts = [mock_part]
    mock_response.candidates = [mock_candidate]
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    data, mime, err, model = asyncio.run(
        generate_meme_image("кіт дивиться в монітор", persona_key="meme_lord", client=mock_client)
    )

    assert data == b"viral_meme_bytes"
    call_kwargs = mock_client.aio.models.generate_content.await_args.kwargs
    assert "viral modern meme concept" in call_kwargs["contents"]

