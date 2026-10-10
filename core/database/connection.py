# Database connection factory and schema initialization for SQLite.
# Configures WAL mode for concurrent read/write safety on Raspberry Pi storage.
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
    # Return rows as dict-like objects for column name access
    conn.row_factory = sqlite3.Row
    # WAL mode improves concurrent reads and writes on flash storage
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema if tables do not exist."""
    path = db_path or get_db_path()
    with get_connection(path) as conn:
        cursor = conn.cursor()
        # Chat messages log table and performance index
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
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp
            ON messages (chat_id, timestamp);
            """
        )

        # Table for FinOps token metrics and cost accounting
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
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp
            ON token_usage (timestamp);
            """
        )

        # Table for access control whitelisting
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

        # Table for user persona preferences
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_personas (
                user_id INTEGER PRIMARY KEY,
                persona_key TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Table for per-chat AI reaction switches
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
