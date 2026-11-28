from app.clients.apertus import Message
from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)


def plan_prompt(
    facts: str, signals: str, request: str | None, existing: list[str] | None
) -> list[Message]:
    """The board plan for one customer: their first boards, or one board for `request`."""
    names = "" if not existing else PROMPTS["existing"].format(names=", ".join(existing))
    shared = {
        "examples": PROMPTS["plan_examples"].format(),
        "existing": names,
        "facts": facts,
        "signals": signals,
    }
    if request is None:
        user = PROMPTS["plan_first"].format(**shared)
    else:
        user = PROMPTS["plan_request"].format(request=request.replace('"', "'"), **shared)
    return [
        {"role": "system", "content": PROMPTS["plan_system"].format()},
        {"role": "user", "content": user},
    ]
