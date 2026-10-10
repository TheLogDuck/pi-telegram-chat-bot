# Access control module for tracking authorized users and group chats.
import asyncio
from datetime import datetime, timezone
from typing import Optional

from core.database.connection import get_connection, get_db_path


def is_entity_approved(
    entity_type: str,
    entity_id: int,
    db_path: Optional[str] = None,
) -> bool:
    """Checks whether a user or chat has an approved status in access_grants.
    
    A return value of True indicates the entity is authorized to interact with the bot.
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


# Asynchronous wrappers delegating blocking SQLite queries to worker threads.
# Running SQLite in thread workers prevents blocking the async event loop on Raspberry Pi 3B+.

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
