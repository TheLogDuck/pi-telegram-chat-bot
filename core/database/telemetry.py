# Token usage tracking, telemetry persistence, and cost analytics.
# Records prompt/completion token consumption per feature and computes daily/all-time metrics.
import asyncio
from datetime import datetime, timezone
from typing import Optional
from .connection import get_connection, get_db_path, init_db


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

        # Query breakdown by bot feature (e.g., chat, news, roast, reaction)
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
