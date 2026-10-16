# Listener module to passively record incoming text messages into the database.
# Implements an in-memory queue to batch inserts every 5 seconds, protecting MicroSD endurance.
import asyncio
from datetime import datetime, timezone
from typing import Optional
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from core.database.messages import async_save_messages_batch
from core.logger import setup_logger

logger = setup_logger("listener")

# Default periodic interval in seconds to flush queued messages to SQLite
DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0

# In-memory FIFO queue to hold uncommitted incoming messages
_MESSAGE_QUEUE: asyncio.Queue = asyncio.Queue()


async def flush_message_queue(db_path: Optional[str] = None) -> int:
    """Drains pending messages from the queue and commits them in a single batch.

    Extracts all currently pending items without blocking new additions,
    reducing SQLite lock contention to a single brief transaction.
    """
    batch = []
    while not _MESSAGE_QUEUE.empty():
        try:
            item = _MESSAGE_QUEUE.get_nowait()
            batch.append(item)
            _MESSAGE_QUEUE.task_done()
        except asyncio.QueueEmpty:
            break

    if not batch:
        return 0

    try:
        inserted = await async_save_messages_batch(batch, db_path=db_path)
        logger.debug(f"Flushed batch of {inserted} messages to SQLite.")
        return inserted
    except Exception as exc:
        logger.error(f"Failed to flush message batch to SQLite: {exc}")
        return 0


async def message_batch_worker(
    interval: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
    db_path: Optional[str] = None,
) -> None:
    """Background worker loop that periodically commits queued messages to SQLite.

    Handles asyncio.CancelledError on bot shutdown to ensure no queued messages are lost.
    """
    while True:
        try:
            await asyncio.sleep(interval)
            await flush_message_queue(db_path=db_path)
        except asyncio.CancelledError:
            # Shutdown requested: perform final flush to persist pending chat history
            await flush_message_queue(db_path=db_path)
            break
        except Exception as exc:
            logger.error(f"Unexpected error in message batch worker: {exc}")


async def passive_message_listener(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Silently enqueues incoming text messages into memory without blocking SQLite.

    Takes less than a microsecond in RAM, keeping the update loop completely responsive.
    """
    if not update.effective_message or not update.effective_message.text:
        return

    # Extract user and chat metadata safely
    message = update.effective_message
    chat_id = update.effective_chat.id if update.effective_chat else 0
    user_id = update.effective_user.id if update.effective_user else 0
    username = update.effective_user.username if update.effective_user else None
    text = message.text

    # Telegram message timestamp formatted in ISO-8601
    timestamp = message.date.isoformat() if message.date else datetime.now(timezone.utc).isoformat()

    # Enqueue in memory instead of immediately opening an SQLite transaction
    _MESSAGE_QUEUE.put_nowait((chat_id, user_id, username, text, timestamp))


def register_listener(app: Application) -> None:
    """Registers the passive logging handler in handler group -2.

    Handler group -2 runs first to record all messages before the auth gatekeeper
    (group -1) and command handlers (group 0).
    """
    app.add_handler(
        MessageHandler(filters.TEXT, passive_message_listener),
        group=-2,
    )
