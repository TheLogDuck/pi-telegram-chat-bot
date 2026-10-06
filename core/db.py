# Core database utility using Python standard library SQLite
import os
import sqlite3

DB_PATH = os.getenv("DATABASE_PATH", "bot_data.db")

def get_connection() -> sqlite3.Connection:
    """Creates and returns a connection to the SQLite database."""
    # SQLite requires no server daemon, making it ideal for low-resource environments
    conn = sqlite3.connect(DB_PATH)
    # Enable name-based column access on returned rows
    conn.row_factory = sqlite3.Row
    return conn
