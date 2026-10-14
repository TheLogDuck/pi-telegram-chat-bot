# Emoji reaction evaluation module.
from typing import Optional
import sys
from google import genai
from google.genai import types
from core.logger import setup_logger
from core.personas import get_persona
from .client import get_gemini_client
from .config import ALLOWED_TELEGRAM_REACTIONS, get_candidate_reaction_models
from .telemetry import record_usage

logger = setup_logger("llm.reactions")


async def _dispatch_record_usage(
    response: object,
    model_name: str,
    feature: str,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """Dispatches token recording, respecting any active patches on core.llm.record_usage."""
    llm_mod = sys.modules.get("core.llm")
    recorder = getattr(llm_mod, "record_usage", record_usage) if llm_mod else record_usage
    await recorder(response, model_name, feature, chat_id, user_id)


def _build_reaction_prompt(
    current_message: str,
    chat_history: list[dict],
    author_name: Optional[str] = None,
) -> str:
    """Formats the conversational context and current message for the reaction decision."""
    history_lines = []
    for item in chat_history:
        uname = item.get("username") or "User"
        txt = item.get("text", "").strip()
        if txt:
            history_lines.append(f"- {uname}: {txt}")

    context_block = "\n".join(history_lines) if history_lines else "(No previous messages)"
    author_label = author_name or "User"
    return (
        f"Context of recent chat messages:\n{context_block}\n\n"
        f"New message from {author_label}:\n\"{current_message.strip()}\"\n\n"
        "Decide: Should you react with an emoji, or NONE?"
    )


def _build_reaction_system_instruction(persona_key: Optional[str]) -> str:
    """Builds a system prompt instructing the model to pick ONE emoji or NONE."""
    persona = get_persona(persona_key)
    return (
        f"You are a Telegram bot with the following persona: {persona.name} ({persona.description}).\n"
        "Your task is to analyze the recent conversation and determine whether to react to the new message.\n"
        "RULES:\n"
        "1. Respond with EXACTLY ONE emoji from standard Telegram reactions, OR the word NONE.\n"
        "2. Only react if the message strongly warrants an emotional reaction fitting your persona. "
        "For ordinary chatter, greetings, or neutral statements, respond with NONE.\n"
        "3. Output ONLY the single emoji or NONE. No explanations, words, markdown, or punctuation."
    )


async def decide_message_reaction(
    current_message: str,
    chat_history: list[dict],
    persona_key: Optional[str] = None,
    author_name: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Evaluates whether to set an emoji reaction on a message based on context and persona."""
    if not current_message or not current_message.strip():
        return None, None

    prompt = _build_reaction_prompt(current_message, chat_history, author_name)
    config = types.GenerateContentConfig(
        system_instruction=_build_reaction_system_instruction(persona_key),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    llm_client = client or get_gemini_client()

    for model_name in get_candidate_reaction_models():
        try:
            response = await llm_client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            await _dispatch_record_usage(response, model_name, "reaction", chat_id, user_id)
            raw = (response.text or "").strip().strip("\"'").strip()
            if not raw or raw.upper() == "NONE":
                return None, model_name
            if raw in ALLOWED_TELEGRAM_REACTIONS:
                return raw, model_name
            logger.info(f"Model {model_name} suggested invalid or unwhitelisted reaction: {raw}")
            return None, model_name
        except Exception as exc:
            logger.warning(f"Reaction evaluation with {model_name} failed: {exc}. Trying next...")
            continue

    logger.error("All candidate reaction models exhausted.")
    return None, None
