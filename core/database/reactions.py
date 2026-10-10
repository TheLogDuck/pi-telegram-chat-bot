# Per-chat AI reaction configuration and state persistence.
# Manages enabling, disabling, and toggling reactions per chat in SQLite.
import asyncio
from datetime import datetime, timezone
from typing import Optional
from .connection import get_connection, get_db_path


def is_reaction_enabled(chat_id: int, db_path: Optional[str] = None) -> bool:
    """Checks whether automatic message reactions are enabled for a specific chat.

    Returns False if the chat record is not found or enabled is 0.
    """
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT enabled FROM chat_reaction_settings WHERE chat_id = ?;",
            (chat_id,),
        )
        row = cursor.fetchone()
        return bool(row and row["enabled"] == 1)


def set_reaction_enabled(
    chat_id: int,
    enabled: bool,
    db_path: Optional[str] = None,
) -> None:
    """Updates or inserts the reaction enabled status for a chat using UPSERT."""
    path = db_path or get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    val = 1 if enabled else 0
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_reaction_settings (chat_id, enabled, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = excluded.updated_at;
            """,
            (chat_id, val, now),
        )
        conn.commit()


def toggle_reaction_enabled(chat_id: int, db_path: Optional[str] = None) -> bool:
    """Flips the reaction enabled state for a chat and returns the new state."""
    current = is_reaction_enabled(chat_id, db_path)
    new_state = not current
    set_reaction_enabled(chat_id, new_state, db_path)
    return new_state


async def async_is_reaction_enabled(
    chat_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """Non-blocking async wrapper to check if reactions are enabled."""
    return await asyncio.to_thread(is_reaction_enabled, chat_id, db_path)


async def async_set_reaction_enabled(
    chat_id: int,
    enabled: bool,
    db_path: Optional[str] = None,
) -> None:
    """Non-blocking async wrapper to update reaction status."""
    await asyncio.to_thread(set_reaction_enabled, chat_id, enabled, db_path)


async def async_toggle_reaction_enabled(
    chat_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """Non-blocking async wrapper to flip reaction status."""
    return await asyncio.to_thread(toggle_reaction_enabled, chat_id, db_path)
