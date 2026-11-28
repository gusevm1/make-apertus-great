from pydantic import BaseModel, Field

from app.clients.apertus import Message
from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)
CRITERIA = ["hero_question", "about_customer", "titles", "not_empty_or_repeated", "coherent"]


class Criterion(BaseModel):
    name: str = Field(description="One of the criteria named in the instructions.")
    passed: bool
    reason: str = Field(description="One sentence.")


class Verdict(BaseModel):
    criteria: list[Criterion]


def judge_prompt(rubric: str, persona: str, boards: str, request: str | None) -> list[Message]:
    asked = "" if request is None else PROMPTS["judge_request"].format(request=request)
    return [
        {"role": "system", "content": PROMPTS["judge_system"].format(rubric=rubric)},
        {
            "role": "user",
            "content": PROMPTS["judge_user"].format(persona=persona, request=asked, boards=boards),
        },
    ]
