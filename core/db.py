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
        # Table to track access control whitelist approvals for users and group chats
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS access_grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                entity_title TEXT,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                UNIQUE(entity_type, entity_id)
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_access_grants_lookup
            ON access_grants (entity_type, entity_id, status);
            """
        )
        # Table to track user-selected personas across private chats and groups
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_personas (
                user_id INTEGER PRIMARY KEY,
                persona_key TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        # Table to track per-chat reaction switch settings
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_reaction_settings (
                chat_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
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


def is_entity_approved(
    entity_type: str,
    entity_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """Checks whether a user or chat has an approved status in access_grants."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT status FROM access_grants
            WHERE entity_type = ? AND entity_id = ?;
            """,
            (entity_type, entity_id),
        )
        row = cursor.fetchone()
        return bool(row and row["status"] == "approved")


def get_or_create_access_request(
    entity_type: str,
    entity_id: int,
    entity_title: Optional[str] = None,
    db_path: Optional[str] = None,
) -> tuple[str, bool]:
    """Retrieves existing request status, or creates a pending record if new.

    Returns:
        tuple[str, bool]: (status, is_new) where is_new is True if inserted.
    """
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT status FROM access_grants
            WHERE entity_type = ? AND entity_id = ?;
            """,
            (entity_type, entity_id),
        )
        row = cursor.fetchone()
        if row:
            return row["status"], False

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT OR IGNORE INTO access_grants (
                entity_type, entity_id, entity_title, status, requested_at
            ) VALUES (?, ?, ?, 'pending', ?);
            """,
            (entity_type, entity_id, entity_title, now),
        )
        conn.commit()
        return "pending", True


def set_access_status(
    entity_type: str,
    entity_id: int,
    status: str,
    entity_title: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Updates or inserts access status (approved, rejected, pending) for a user or chat."""
    path = db_path or get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO access_grants (
                entity_type, entity_id, entity_title, status, requested_at, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                status = excluded.status,
                reviewed_at = excluded.reviewed_at,
                entity_title = COALESCE(excluded.entity_title, access_grants.entity_title);
            """,
            (entity_type, entity_id, entity_title, status, now, now),
        )
        conn.commit()


def get_all_access_grants(db_path: Optional[str] = None) -> list[dict]:
    """Retrieves all tracked access requests and their statuses."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_type, entity_id, entity_title, status, requested_at, reviewed_at
            FROM access_grants
            ORDER BY requested_at DESC;
            """
        )
        return [dict(row) for row in cursor.fetchall()]


async def async_is_entity_approved(
    entity_type: str,
    entity_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """Non-blocking async wrapper to check if an entity is approved."""
    return await asyncio.to_thread(is_entity_approved, entity_type, entity_id, db_path)


async def async_get_or_create_access_request(
    entity_type: str,
    entity_id: int,
    entity_title: Optional[str] = None,
    db_path: Optional[str] = None,
) -> tuple[str, bool]:
    """Non-blocking async wrapper to fetch or create an access request."""
    return await asyncio.to_thread(
        get_or_create_access_request, entity_type, entity_id, entity_title, db_path
    )


async def async_set_access_status(
    entity_type: str,
    entity_id: int,
    status: str,
    entity_title: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Non-blocking async wrapper to update access status."""
    await asyncio.to_thread(set_access_status, entity_type, entity_id, status, entity_title, db_path)


async def async_get_all_access_grants(db_path: Optional[str] = None) -> list[dict]:
    """Non-blocking async wrapper to list all access grants."""
    return await asyncio.to_thread(get_all_access_grants, db_path)


def get_user_persona(user_id: int, db_path: Optional[str] = None) -> str:
    """Retrieves the configured persona key for a user, defaulting to 'standard'."""
    if not isinstance(user_id, int):
        return "standard"

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
    return "standard"


def set_user_persona(user_id: int, persona_key: str, db_path: Optional[str] = None) -> None:
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


async def async_get_user_persona(user_id: int, db_path: Optional[str] = None) -> str:
    """Non-blocking async wrapper to fetch a user's selected persona."""
    return await asyncio.to_thread(get_user_persona, user_id, db_path)


async def async_set_user_persona(user_id: int, persona_key: str, db_path: Optional[str] = None) -> None:
    """Non-blocking async wrapper to save a user's selected persona."""
    await asyncio.to_thread(set_user_persona, user_id, persona_key, db_path)


def is_reaction_enabled(chat_id: int, db_path: Optional[str] = None) -> bool:
    """Checks whether automatic message reactions are enabled for a specific chat."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT enabled FROM chat_reaction_settings WHERE chat_id = ?;", (chat_id,))
        row = cursor.fetchone()
        return bool(row and row["enabled"] == 1)


def set_reaction_enabled(chat_id: int, enabled: bool, db_path: Optional[str] = None) -> None:
    """Updates or inserts the reaction enabled status for a chat."""
    path = db_path or get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    val = 1 if enabled else 0
    with get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_reaction_settings (chat_id, enabled, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled, updated_at = excluded.updated_at;
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


async def async_is_reaction_enabled(chat_id: int, db_path: Optional[str] = None) -> bool:
    """Non-blocking async wrapper to check if reactions are enabled."""
    return await asyncio.to_thread(is_reaction_enabled, chat_id, db_path)


async def async_set_reaction_enabled(chat_id: int, enabled: bool, db_path: Optional[str] = None) -> None:
    """Non-blocking async wrapper to update reaction status."""
    await asyncio.to_thread(set_reaction_enabled, chat_id, enabled, db_path)


async def async_toggle_reaction_enabled(chat_id: int, db_path: Optional[str] = None) -> bool:
    """Non-blocking async wrapper to flip reaction status."""
    return await asyncio.to_thread(toggle_reaction_enabled, chat_id, db_path)


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

    return "standard"


async def async_get_effective_persona(
    chat_id: int,
    user_id: Optional[int] = None,
    db_path: Optional[str] = None,
) -> str:
    """Non-blocking async wrapper to resolve active persona."""
    return await asyncio.to_thread(get_effective_persona, chat_id, user_id, db_path)










