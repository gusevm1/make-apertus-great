from app.clients.apertus import Message
from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)


def profile_prompt(facts: str, signals: str, heroes: list[str]) -> list[Message]:
    """Who the customer is, their question and the signal that answers it."""
    return [
        {"role": "system", "content": PROMPTS["profile_system"].format()},
        {
            "role": "user",
            "content": PROMPTS["profile_user"].format(
                facts=facts, signals=signals, heroes="\n".join(heroes)
            ),
        },
    ]


def board_prompt(
    facts: str,
    signals: str,
    kind: str,
    question: str,
    hero: str,
    request: str | None,
    existing: list[str] | None,
) -> list[Message]:
    """The tiles of the first boards after the hero, or of one board for `request`."""
    if request is None:
        user = PROMPTS["board_first"].format(
            kind=kind, question=question, hero=hero, facts=facts, signals=signals
        )
    else:
        names = "" if not existing else PROMPTS["existing"].format(names=", ".join(existing))
        user = PROMPTS["board_request"].format(
            request=request.replace('"', "'"), existing=names, facts=facts, signals=signals
        )
    return [
        {"role": "system", "content": PROMPTS["board_system"].format()},
        {"role": "user", "content": user},
    ]
