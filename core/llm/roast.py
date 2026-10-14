# Roast generation module for standup comedy and meme roasts.
from typing import Optional
from google import genai
from google.genai import types
from core.personas import get_persona
from .config import API_ERROR_MESSAGE, get_candidate_models
from .engine import execute_text_generation


def _build_roast_prompt(
    clean_target: str,
    context_messages: Optional[list[str]],
    is_meme_lord: bool,
) -> str:
    """Formats the prompt context for standup comedy or meme-lord roasts."""
    quotes = "\n".join(f"- {msg}" for msg in context_messages) if context_messages else None

    if is_meme_lord:
        if quotes:
            return (
                f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
                f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
                "Обіграй ці цитати через актуальні меми, жизу, базу, крінж або щитпостинг (1-3 абзаци). "
                "Відповідай виключно українською мовою."
            )
        return (
            f"Влаштуй дотепну, постіронічну просмажку користувача @{clean_target} у стилі інтернет-мемів.\n"
            "Цей мембер поки що взагалі мовчить у чаті (мабуть, ловить крінж або боїться спалитися). "
            "Пожартуй над цим у стилі щитпостингу та постиронії (1-2 абзаци). "
            "Відповідай виключно українською мовою."
        )

    if quotes:
        return (
            f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
            f"Ось кілька його останніх реплік у цьому чаті:\n{quotes}\n\n"
            "Обіграй ці цитати або звички у короткій, смішній стендап-прожарці (1-3 абзаци). "
            "Відповідай виключно українською мовою."
        )
    return (
        f"Влаштуй дотепний дружній роаст користувача @{clean_target}.\n"
        "Цей користувач поки що майже нічого не писав у цьому чаті (або майстерно ховається у засідці). "
        "Пожартуй над цим у короткій стендап-прожарці (1-2 абзаци). "
        "Відповідай виключно українською мовою."
    )


async def generate_roast(
    target_name: str,
    context_messages: Optional[list[str]] = None,
    client: Optional[genai.Client] = None,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persona_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Generates a witty standup comedy roast of a user in Ukrainian."""
    clean_target = target_name.lstrip("@").strip()
    active_persona = get_persona(persona_key)
    prompt = _build_roast_prompt(
        clean_target=clean_target,
        context_messages=context_messages,
        is_meme_lord=(active_persona.key == "meme_lord"),
    )

    config = types.GenerateContentConfig(
        system_instruction=active_persona.roast_system_instruction,
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
