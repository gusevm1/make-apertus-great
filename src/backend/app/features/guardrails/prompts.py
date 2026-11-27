from typing import Literal

from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts
from app.features.guardrails.schemas import Advisor, Language

PROMPTS = load_prompts(prompts_py=__file__)


def check_prompt(text: str) -> list[LLMMessage]:
    # Escaped, the message can neither close its block nor open a tag of its own.
    escaped = text.replace("<", "&lt;").replace(">", "&gt;")
    return [
        {"role": "system", "content": PROMPTS["check_system"]},
        {"role": "user", "content": PROMPTS["check_message"].format(text=escaped)},
    ]


def advisor_pointer(advisor: Advisor, language: Language) -> str:
    return PROMPTS[f"advisor_{language}"].format(name=advisor.name, phone=advisor.phone)


def counselling_pointer(language: Language) -> str:
    return PROMPTS[f"counselling_{language}"]


def decline(category: Literal["off_topic", "other_customer"], language: Language) -> str:
    return PROMPTS[f"{category}_{language}"]
