# Unit tests for core/telegram_utils.py.
# Validates mention detection, text cleaning, Markdown to Telegram HTML conversion,
# and safe HTML delivery with plain-text fallback.
import asyncio
from unittest.mock import AsyncMock, MagicMock
from telegram import Message, Update
from telegram.constants import ChatType, ParseMode
from core.telegram_utils import (
    clean_bot_mention,
    is_bot_mentioned,
    markdown_to_telegram_html,
    send_formatted_reply,
)


def test_markdown_to_telegram_html_empty() -> None:
    """Verifies that empty string input returns an empty string."""
    assert markdown_to_telegram_html("") == ""
    assert markdown_to_telegram_html(None) == ""


def test_markdown_to_telegram_html_headers_and_bullets() -> None:
    """Verifies that markdown headers become <b> tags and bullets become •."""
    input_text = "### Головний заголовок\n* Перший пункт\n- Другий пункт"
    converted = markdown_to_telegram_html(input_text)
    assert "<b>Головний заголовок</b>" in converted
    assert "• Перший пункт" in converted
    assert "• Другий пункт" in converted


def test_markdown_to_telegram_html_bold_italic_strikethrough() -> None:
    """Verifies standard formatting: bold, italic, and strikethrough."""
    input_text = "Текст **жирний** і *курсив*, а також ~~закреслено~~."
    converted = markdown_to_telegram_html(input_text)
    assert "<b>жирний</b>" in converted
    assert "<i>курсив</i>" in converted
    assert "<s>закреслено</s>" in converted


def test_markdown_to_telegram_html_preserves_snake_case() -> None:
    """Verifies that underscores inside variable names are not turned into italics."""
    input_text = "Змінна user_id_value не повинна ламатися."
    converted = markdown_to_telegram_html(input_text)
    assert "user_id_value" in converted
    assert "<i>" not in converted


def test_markdown_to_telegram_html_escapes_raw_html() -> None:
    """Verifies that raw <, >, and & characters outside code are escaped."""
    input_text = "Умова: x < 10 & y > 5"
    converted = markdown_to_telegram_html(input_text)
    assert "x &lt; 10 &amp; y &gt; 5" in converted


def test_markdown_to_telegram_html_code_blocks_and_inline() -> None:
    """Verifies that code blocks and inline code are protected and properly formatted."""
    input_text = (
        "Подивіться на `var_name`:\n"
        "```python\n"
        "def hello():\n"
        "    return a * b < c\n"
        "```"
    )
    converted = markdown_to_telegram_html(input_text)
    assert "<code>var_name</code>" in converted
    assert '<pre><code class="language-python">' in converted
    assert "return a * b &lt; c" in converted


def test_markdown_to_telegram_html_links() -> None:
    """Verifies that standard markdown links convert to Telegram <a> tags."""
    input_text = "Дивіться [новини](https://news.google.com) тут."
    converted = markdown_to_telegram_html(input_text)
    assert '<a href="https://news.google.com">новини</a>' in converted


def test_send_formatted_reply_success() -> None:
    """Verifies that send_formatted_reply calls reply_text with ParseMode.HTML."""
    mock_message = MagicMock(spec=Message)
    mock_message.reply_text = AsyncMock()

    asyncio.run(send_formatted_reply(mock_message, "Привіт **світ**!"))

    mock_message.reply_text.assert_awaited_once_with(
        "Привіт <b>світ</b>!",
        parse_mode=ParseMode.HTML,
    )


def test_send_formatted_reply_fallback_on_error() -> None:
    """Verifies that if HTML parsing raises an error, it falls back to plain text."""
    mock_message = MagicMock(spec=Message)
    mock_message.reply_text = AsyncMock()
    # First call with HTML fails, second call with plain text succeeds
    mock_message.reply_text.side_effect = [
        Exception("Can't parse entities"),
        None,
    ]

    asyncio.run(send_formatted_reply(mock_message, "Привіт **світ**!"))

    assert mock_message.reply_text.await_count == 2
    mock_message.reply_text.assert_awaited_with("Привіт **світ**!")
