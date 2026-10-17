# Per-chat language preference storage and retrieval in SQLite.
# Configures default 'en' language for unconfigured chats.
import asyncio
from datetime import datetime, timezone
from typing import Optional
from core.languages import DEFAULT_LANGUAGE, is_supported_language
from .connection import get_connection, get_db_path


def get_chat_language(chat_id: int, db_path: Optional[str] = None) -> str:
    """Retrieves the active language code for a chat, defaulting to 'en'."""
    if not isinstance(chat_id, int):
        return DEFAULT_LANGUAGE

    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT language_code FROM chat_languages WHERE chat_id = ?;",
            (chat_id,),
        )
        row = cursor.fetchone()
        if row and row["language_code"]:
            return row["language_code"]
    return DEFAULT_LANGUAGE


def set_chat_language(
    chat_id: int,
    language_code: str,
    db_path: Optional[str] = None,
) -> None:
    """Persists or updates the language code for a chat using SQLite UPSERT."""
    if not isinstance(chat_id, int) or not is_supported_language(language_code):
        return

    path = db_path or get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_languages (chat_id, language_code, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                language_code = excluded.language_code,
                updated_at = excluded.updated_at;
            """,
            (chat_id, language_code, now),
        )
        conn.commit()


async def async_get_chat_language(
    chat_id: int,
    db_path: Optional[str] = None,
) -> str:
    """Non-blocking async wrapper to fetch a chat's language."""
    return await asyncio.to_thread(get_chat_language, chat_id, db_path)


async def async_set_chat_language(
    chat_id: int,
    language_code: str,
    db_path: Optional[str] = None,
) -> None:
    """Non-blocking async wrapper to save a chat's language."""
    await asyncio.to_thread(set_chat_language, chat_id, language_code, db_path)
