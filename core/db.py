# Database management module using Python's standard library sqlite3.
# Keeps memory usage near 0 MB additional overhead compared to heavy ORMs.
import asyncio
from datetime import datetime, timedelta, timezone
import os
import sqlite3
from typing import Optional

DEFAULT_DB_PATH = "bot_memory.db"
DEFAULT_RETENTION_DAYS = 30

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
        # Table to track LLM token consumption and estimated dollar costs
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                chat_id INTEGER,
                user_id INTEGER,
                model TEXT NOT NULL,
                feature TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL
            );
            """
        )
        # Index on timestamp speeds up range filters for daily usage stats
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp
            ON token_usage (timestamp);
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


def save_token_usage(
    model: str,
    feature: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Inserts a single token consumption and cost record into SQLite."""
    if timestamp is None:
        # Normalize to UTC ISO-8601 for consistent day/month filtering
        timestamp = datetime.now(timezone.utc).isoformat()

    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO token_usage (
                timestamp, chat_id, user_id, model, feature,
                prompt_tokens, completion_tokens, total_tokens, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                timestamp, chat_id, user_id, model, feature,
                prompt_tokens, completion_tokens, total_tokens, cost_usd,
            ),
        )
        conn.commit()
        return cursor.lastrowid


async def async_save_token_usage(
    model: str,
    feature: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Non-blocking async wrapper delegating token log write to a worker thread."""
    return await asyncio.to_thread(
        save_token_usage,
        model,
        feature,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        cost_usd,
        chat_id,
        user_id,
        timestamp,
        db_path,
    )


def get_token_usage_stats(db_path: Optional[str] = None) -> dict:
    """Aggregates all-time and current UTC-day token usage and estimated costs."""
    path = db_path or get_db_path()
    # Ensure tables exist prior to executing aggregate queries
    init_db(path)
    # UTC midnight timestamp for today's filter
    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%d") + "T00:00:00"

    with get_connection(path) as conn:
        cursor = conn.cursor()

        # Query today's aggregated usage
        cursor.execute(
            """
            SELECT
                COUNT(*) as calls_count,
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0.0) as cost_usd
            FROM token_usage
            WHERE timestamp >= ?;
            """,
            (today_start,),
        )
        today_row = cursor.fetchone()

        # Query all-time aggregated usage
        cursor.execute(
            """
            SELECT
                COUNT(*) as calls_count,
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0.0) as cost_usd
            FROM token_usage;
            """
        )
        total_row = cursor.fetchone()

        # Query breakdown by bot feature (e.g., chat, news, roast)
        cursor.execute(
            """
            SELECT
                feature,
                COUNT(*) as calls_count,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0.0) as cost_usd
            FROM token_usage
            GROUP BY feature;
            """
        )
        feature_rows = cursor.fetchall()
        by_feature = {
            row["feature"]: {
                "calls": row["calls_count"],
                "tokens": row["total_tokens"],
                "cost_usd": row["cost_usd"],
            }
            for row in feature_rows
        }

        return {
            "today": {
                "calls": today_row["calls_count"],
                "prompt_tokens": today_row["prompt_tokens"],
                "completion_tokens": today_row["completion_tokens"],
                "total_tokens": today_row["total_tokens"],
                "cost_usd": today_row["cost_usd"],
            },
            "total": {
                "calls": total_row["calls_count"],
                "prompt_tokens": total_row["prompt_tokens"],
                "completion_tokens": total_row["completion_tokens"],
                "total_tokens": total_row["total_tokens"],
                "cost_usd": total_row["cost_usd"],
            },
            "by_feature": by_feature,
        }


async def async_get_token_usage_stats(db_path: Optional[str] = None) -> dict:
    """Non-blocking async wrapper to aggregate stats off the main thread."""
    return await asyncio.to_thread(get_token_usage_stats, db_path)


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



