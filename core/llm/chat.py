# Conversational text generation feature module.
from typing import Optional
from google import genai
from google.genai import types
from core.personas import get_persona
from .config import API_ERROR_MESSAGE, get_candidate_models
from .engine import execute_text_generation


def _inject_language_directive(instruction: str, language: Optional[str]) -> str:
    """Injects the requested output language directive into the persona system instruction."""
    if not language or language == "uk":
        return instruction

    from core.languages import get_language_directive

    directive = get_language_directive(language)
    # Replace Ukrainian-only output constraints to avoid contradictory prompts
    ua_phrases = [
        "Проте свої власні відповіді ти ЗАВЖДИ формулюєш виключно українською мовою.",
        "Свої власні відповіді ти ЗАВЖДИ формулюєш виключно українською мовою.",
        "Ти ЗАВЖДИ відповідаєш виключно українською мовою.",
    ]
    for phrase in ua_phrases:
        if phrase in instruction:
            return instruction.replace(phrase, directive)

    # Fallback: append directive to prompt
    return f"{instruction}\n\n{directive}"


async def generate_response(
    prompt: str,
    system_instruction: Optional[str] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
    language: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Asynchronously generates a conversational text response from the Gemini model."""
    if not prompt or not prompt.strip():
        return "Будь ласка, вкажіть повідомлення або запитання.", None

    active_persona = get_persona(persona_key)
    base_instruction = system_instruction or active_persona.chat_system_instruction
    effective_instruction = _inject_language_directive(base_instruction, language)

    config = types.GenerateContentConfig(
        system_instruction=effective_instruction,
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
