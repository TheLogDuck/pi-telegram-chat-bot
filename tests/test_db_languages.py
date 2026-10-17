# Unit tests for per-chat language storage in SQLite.
import asyncio
import tempfile
import pytest
from core.database.connection import init_db
from core.database.languages import (
    async_get_chat_language,
    async_set_chat_language,
    get_chat_language,
    set_chat_language,
)


@pytest.fixture
def temp_db_path() -> str:
    """Creates a temporary SQLite database initialized with tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    return path


def test_get_chat_language_default_is_en(temp_db_path: str) -> None:
    """Verifies that an unconfigured chat defaults to English ('en')."""
    lang = get_chat_language(-10012345, db_path=temp_db_path)
    assert lang == "en"


def test_set_and_get_chat_language(temp_db_path: str) -> None:
    """Verifies persisting and retrieving a language for a specific chat."""
    chat_id = -1009999
    set_chat_language(chat_id, "ru", db_path=temp_db_path)
    assert get_chat_language(chat_id, db_path=temp_db_path) == "ru"

    # Verify updating the language for the same chat (UPSERT behavior)
    set_chat_language(chat_id, "de", db_path=temp_db_path)
    assert get_chat_language(chat_id, db_path=temp_db_path) == "de"


def test_async_get_and_set_chat_language(temp_db_path: str) -> None:
    """Verifies non-blocking asynchronous database wrappers."""
    chat_id = 555666

    async def run_async_flow() -> None:
        default_lang = await async_get_chat_language(chat_id, db_path=temp_db_path)
        assert default_lang == "en"

        await async_set_chat_language(chat_id, "uk", db_path=temp_db_path)
        updated_lang = await async_get_chat_language(chat_id, db_path=temp_db_path)
        assert updated_lang == "uk"

    asyncio.run(run_async_flow())
