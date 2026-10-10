# Message logging, history retrieval, and retention cleanup module.
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.database.connection import (
    DEFAULT_RETENTION_DAYS,
    get_connection,
    get_db_path,
    init_db,
)


def save_message(
    chat_id: int,
    user_id: int,
    username: Optional[str],
    text: str,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Synchronous worker function to insert a message into SQLite."""
    if timestamp is None:
        # Standardize timestamps in UTC ISO-8601 format
        timestamp = datetime.now(timezone.utc).isoformat()

    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (chat_id, user_id, username, text, timestamp)
            VALUES (?, ?, ?, ?, ?);
            """,
            (chat_id, user_id, username, text, timestamp),
        )
        conn.commit()
        return cursor.lastrowid


async def async_save_message(
    chat_id: int,
    user_id: int,
    username: Optional[str],
    text: str,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Non-blocking async wrapper that delegates disk I/O to a worker thread.

    This prevents blocking the Telegram event loop while maintaining zero
    external library footprint.
    """
    return await asyncio.to_thread(
        save_message,
        chat_id,
        user_id,
        username,
        text,
        timestamp,
        db_path,
    )


def get_chat_messages(
    chat_id: int,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
    before_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Unified function to retrieve recent non-command messages in chronological order."""
    path = db_path or get_db_path()
    clean_username = username.lstrip("@").lower() if username else None
    query = "SELECT id, user_id, username, text, timestamp FROM messages WHERE chat_id = ? AND text NOT LIKE '/%'"
    params: list = [chat_id]

    if clean_username and user_id is not None:
        query += " AND (LOWER(username) = ? OR user_id = ?)"
        params.extend([clean_username, user_id])
    elif clean_username:
        query += " AND LOWER(username) = ?"
        params.append(clean_username)
    elif user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    if before_id is not None:
        query += " AND id < ?"
        params.append(before_id)

    query += " ORDER BY id DESC LIMIT ?;"
    params.append(limit)

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in reversed(rows)]


def get_user_messages(
    chat_id: int,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> list[str]:
    """Retrieves recent non-command message text strings from a specific user."""
    if not username and user_id is None:
        return []
    messages = get_chat_messages(
        chat_id=chat_id, username=username, user_id=user_id, limit=limit, db_path=db_path
    )
    return [m["text"] for m in messages]


async def async_get_chat_messages(
    chat_id: int,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
    before_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Non-blocking async wrapper to retrieve chat messages."""
    return await asyncio.to_thread(
        get_chat_messages, chat_id, username, user_id, limit, before_id, db_path
    )


async def async_get_user_messages(
    chat_id: int,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> list[str]:
    """Non-blocking async wrapper to retrieve a user's recent messages from SQLite."""
    return await asyncio.to_thread(
        get_user_messages,
        chat_id,
        username,
        user_id,
        limit,
        db_path,
    )


def get_recent_chat_messages(
    chat_id: int,
    limit: int = 5,
    before_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Retrieves recent non-command messages from all users in a chat in chronological order."""
    return get_chat_messages(
        chat_id=chat_id, limit=limit, before_id=before_id, db_path=db_path
    )


async def async_get_recent_chat_messages(
    chat_id: int,
    limit: int = 5,
    before_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Non-blocking async wrapper to fetch recent chat messages."""
    return await asyncio.to_thread(get_recent_chat_messages, chat_id, limit, before_id, db_path)


def cleanup_old_messages(
    retention_days: Optional[int] = None,
    db_path: Optional[str] = None,
) -> int:
    """Prunes messages older than retention_days to protect MicroSD storage.

    Args:
        retention_days: Maximum age of messages in days to keep. Defaults to DEFAULT_RETENTION_DAYS.
        db_path: Optional database file path.

    Returns:
        Number of deleted rows.
    """
    days = retention_days if retention_days is not None else DEFAULT_RETENTION_DAYS
    path = db_path or get_db_path()
    init_db(path)

    # Compute cutoff timestamp in UTC ISO-8601 format
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE timestamp < ?;", (cutoff,))
        deleted_count = cursor.rowcount
        conn.commit()

        # Checkpoint committed WAL pages back to the database file
        conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        return deleted_count


async def async_cleanup_old_messages(
    retention_days: Optional[int] = None,
    db_path: Optional[str] = None,
) -> int:
    """Non-blocking async wrapper delegating message cleanup to worker thread."""
    return await asyncio.to_thread(cleanup_old_messages, retention_days, db_path)
