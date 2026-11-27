from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)


def correction_prompt(answer: str, missing: list[str], data: str) -> list[LLMMessage]:
    # Escaped, the data can neither close its block nor open a tag of its own.
    escaped = data.replace("<", "&lt;").replace(">", "&gt;")
    content = PROMPTS["correction_message"].format(
        missing=", ".join(missing), answer=answer, data=escaped
    )
    return [
        {"role": "system", "content": PROMPTS["correction_system"]},
        {"role": "user", "content": content},
    ]
