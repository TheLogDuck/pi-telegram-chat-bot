# User persona preference storage and resolution hierarchy.
# Manages user-selected personas ('standard', 'cynic', 'meme_lord') in SQLite.
import asyncio
from datetime import datetime, timezone
from typing import Optional
from .connection import get_connection, get_db_path

DEFAULT_PERSONA = "standard"


def get_user_persona(user_id: int, db_path: Optional[str] = None) -> str:
    """Retrieves the configured persona key for a user, defaulting to 'standard'."""
    if not isinstance(user_id, int):
        return DEFAULT_PERSONA

    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT persona_key FROM user_personas
            WHERE user_id = ?;
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["persona_key"]
    return DEFAULT_PERSONA


def set_user_persona(
    user_id: int,
    persona_key: str,
    db_path: Optional[str] = None,
) -> None:
    """Persists or updates the active persona key chosen by a specific user."""
    if not isinstance(user_id, int):
        return

    path = db_path or get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_personas (user_id, persona_key, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                persona_key = excluded.persona_key,
                updated_at = excluded.updated_at;
            """,
            (user_id, persona_key, now),
        )
        conn.commit()


async def async_get_user_persona(
    user_id: int,
    db_path: Optional[str] = None,
) -> str:
    """Non-blocking async wrapper to fetch a user's selected persona."""
    return await asyncio.to_thread(get_user_persona, user_id, db_path)


async def async_set_user_persona(
    user_id: int,
    persona_key: str,
    db_path: Optional[str] = None,
) -> None:
    """Non-blocking async wrapper to save a user's selected persona."""
    await asyncio.to_thread(set_user_persona, user_id, persona_key, db_path)


def get_effective_persona(
    chat_id: int,
    user_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> str:
    """Resolves persona with precedence: chat persona -> sender persona -> 'standard'."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        # 1. Check if chat has a designated persona
        cursor.execute("SELECT persona_key FROM user_personas WHERE user_id = ?;", (chat_id,))
        chat_row = cursor.fetchone()
        if chat_row:
            return chat_row["persona_key"]

        # 2. Check if the user has a personal persona
        if user_id is not None:
            cursor.execute("SELECT persona_key FROM user_personas WHERE user_id = ?;", (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                return user_row["persona_key"]

    return DEFAULT_PERSONA


async def async_get_effective_persona(
    chat_id: int,
    user_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> str:
    """Non-blocking async wrapper to resolve active persona."""
    return await asyncio.to_thread(get_effective_persona, chat_id, user_id, db_path)
