from app.clients.apertus import Message
from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)


def profile_prompt(facts: str, signals: str, heroes: list[str], booked: str) -> list[Message]:
    """Who the customer is, their question and the signal that answers it."""
    return [
        {"role": "system", "content": PROMPTS["profile_system"].format()},
        {
            "role": "user",
            "content": PROMPTS["profile_user"].format(
                facts=facts,
                signals=signals,
                heroes="\n".join(heroes),
                booked="" if not booked else PROMPTS["profile_booked"].format(booked=booked),
            ),
        },
    ]


def board_prompt(
    facts: str,
    signals: str,
    kind: str,
    question: str,
    hero: str,
) -> list[Message]:
    """The tiles of the first boards after the hero."""
    user = PROMPTS["board_first"].format(
        kind=kind, question=question, hero=hero, facts=facts, signals=signals
    )
    return [
        {"role": "system", "content": PROMPTS["board_system"].format()},
        {"role": "user", "content": user},
    ]


def request_prompt(
    request: str, lists: str, signals: str, existing: list[str] | None
) -> list[Message]:
    """Which of the customer's things one requested board is about."""
    names = "" if not existing else PROMPTS["existing"].format(names=", ".join(existing))
    user = PROMPTS["request_user"].format(
        request=request.replace('"', "'"), existing=names, lists=lists, signals=signals
    )
    return [
        {"role": "system", "content": PROMPTS["request_system"].format()},
        {"role": "user", "content": user},
    ]


def entry_prompt(request: str, entry: str) -> list[Message]:
    """Whether one entry of the customer's data is itself about the request."""
    return [
        {"role": "system", "content": PROMPTS["entry_system"].format()},
        {
            "role": "user",
            "content": PROMPTS["entry_user"].format(request=request.replace('"', "'"), entry=entry),
        },
    ]
