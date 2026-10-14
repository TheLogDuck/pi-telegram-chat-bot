# Roast generation module for standup comedy and meme roasts.
from typing import Optional
from google import genai
from google.genai import types
from core.personas import get_persona
from .config import API_ERROR_MESSAGE, get_candidate_models
from .engine import execute_text_generation


def _inject_language_directive(instruction: str, language: Optional[str]) -> str:
    """Injects the requested output language directive into roast instructions."""
    if not language or language == "uk":
        return instruction

    from core.languages import get_language_directive

    directive = get_language_directive(language)
    ua_phrases = [
        "Ти ЗАВЖДИ відповідаєш виключно українською мовою.",
        "Відповідай виключно українською мовою.",
    ]
    for phrase in ua_phrases:
        if phrase in instruction:
            instruction = instruction.replace(phrase, directive)
    return instruction


def _build_roast_prompt(
    clean_target: str,
    context_messages: Optional[list[str]],
    is_meme_lord: bool,
    language: Optional[str] = None,
) -> str:
    """Formats the prompt context for standup comedy or meme-lord roasts."""
    quotes = "\n".join(f"- {msg}" for msg in context_messages) if context_messages else None

    if is_meme_lord:
        if quotes:
            base_prompt = (
                f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
                f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
                "Обіграй ці цитати через актуальні меми, жизу, базу, крінж або щитпостинг (1-3 абзаци). "
                "Відповідай виключно українською мовою."
            )
        else:
            base_prompt = (
                f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
                "Цей мембер поки що взагалі мовчить у чаті (мабуть, ловить крінж або боїться спалитися). "
                "Пожартуй над цим у стилі щитпостингу та постиронії (1-2 абзаци). "
                "Відповідай виключно українською мовою."
            )
    else:
        if quotes:
            base_prompt = (
                f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
                f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
                "Обіграй ці цитати або звички у короткій, смішній стендап-прожарці (1-3 абзаци). "
                "Відповідай виключно українською мовою."
            )
        else:
            base_prompt = (
                f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
                "Цей користувач поки що майже нічого не писав у цьому чаті (або майстерно ховається у засідці). "
                "Пожартуй над цим у короткій стендап-прожарці (1-2 абзаци). "
                "Відповідай виключно українською мовою."
            )

    return _inject_language_directive(base_prompt, language)


async def generate_roast(
    target_name: str,
    context_messages: Optional[list[str]] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
    language: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Generates a witty standup comedy roast of a user."""
    clean_target = target_name.lstrip("@").strip()
    active_persona = get_persona(persona_key)
    prompt = _build_roast_prompt(
        clean_target=clean_target,
        context_messages=context_messages,
        is_meme_lord=(active_persona.key == "meme_lord"),
        language=language,
    )

    base_system_instruction = active_persona.roast_system_instruction
    effective_instruction = _inject_language_directive(base_system_instruction, language)

    config = types.GenerateContentConfig(
        system_instruction=effective_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    text, model = await execute_text_generation(
        prompt=prompt,
        config=config,
        candidates=get_candidate_models(),
        feature="roast",
        client=client,
        chat_id=chat_id,
        user_id=user_id,
    )
    return (text, model) if text else (API_ERROR_MESSAGE, None)
