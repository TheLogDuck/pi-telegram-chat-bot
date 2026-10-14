# Conversational text generation feature module.
from typing import Optional
from google import genai
from google.genai import types
from core.personas import get_persona
from .config import API_ERROR_MESSAGE, get_candidate_models
from .engine import execute_text_generation


async def generate_response(
    prompt: str,
    system_instruction: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a conversational text response from the Gemini model."""
    if not prompt or not prompt.strip():
        return "Будь ласка, вкажіть повідомлення або запитання.", None

    active_persona = get_persona(persona_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction or active_persona.chat_system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    text, model = await execute_text_generation(
        prompt=prompt.strip(),
        config=config,
        candidates=get_candidate_models(),
        feature="chat",
        client=client,
        chat_id=chat_id,
        user_id=user_id,
    )
    return (text, model) if text else (API_ERROR_MESSAGE, None)
