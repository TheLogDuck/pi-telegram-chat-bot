# Database management module using Python's standard library sqlite3.
# Keeps memory usage near 0 MB additional overhead compared to heavy ORMs.
import asyncio
from datetime import datetime, timezone
import os
import sqlite3
from typing import Optional

DEFAULT_DB_PATH = "bot_memory.db"

def get_db_path() -> str:
    """Returns database file path from environment or default."""
    return os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Establishes an SQLite connection configured for concurrent safety."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    # Return rows as dict-like objects for easier column access
    conn.row_factory = sqlite3.Row
    # WAL mode improves concurrent reads and writes on Raspberry Pi flash storage
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema if tables do not exist."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                text TEXT,
                timestamp TEXT NOT NULL
            );
            """
        )
        # Index on chat_id and timestamp speeds up queries for message history
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp
            ON messages (chat_id, timestamp);
            """
        )
        conn.commit()

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


def get_user_messages(
    chat_id: int,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 5,
    db_path: Optional[str] = None,
) -> list[str]:
    """Retrieves recent non-command messages from a user in a specific chat."""
    path = db_path or get_db_path()
    clean_username = username.lstrip("@").lower() if username else None

    with get_connection(path) as conn:
        cursor = conn.cursor()
        # Query messages matching either username or user_id, excluding slash commands
        if clean_username and user_id:
            cursor.execute(
                """
                SELECT text FROM messages
                WHERE chat_id = ?
                  AND (LOWER(username) = ? OR user_id = ?)
                  AND text NOT LIKE '/%'
                ORDER BY id DESC
                LIMIT ?;
                """,
                (chat_id, clean_username, user_id, limit),
            )
        elif clean_username:
            cursor.execute(
                """
                SELECT text FROM messages
                WHERE chat_id = ?
                  AND LOWER(username) = ?
                  AND text NOT LIKE '/%'
                ORDER BY id DESC
                LIMIT ?;
                """,
                (chat_id, clean_username, limit),
            )
        elif user_id:
            cursor.execute(
                """
                SELECT text FROM messages
                WHERE chat_id = ?
                  AND user_id = ?
                  AND text NOT LIKE '/%'
                ORDER BY id DESC
                LIMIT ?;
                """,
                (chat_id, user_id, limit),
            )
        else:
            return []

        rows = cursor.fetchall()
        # Return chronologically (oldest first) so the AI reads the conversation naturally
        return [row["text"] for row in reversed(rows)]


async def async_get_user_messages(
    chat_id: int,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 5,
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
