from app.clients.apertus import Message
from app.core.prompts import load_prompts
from app.features.documents.schemas import FIELD_NAMES, DocumentKind

PROMPTS = load_prompts(prompts_py=__file__)


def describe_prompt(markdown: str) -> list[Message]:
    field_names = "\n".join(
        f"  - {kind}: {', '.join(names)}" for kind, names in FIELD_NAMES.items()
    )
    system = PROMPTS["describe_system"].format(
        kinds=", ".join(DocumentKind.__args__), field_names=field_names
    )
    # Escaped, the document can neither close its block nor open a tag of its own.
    text = markdown.replace("<", "&lt;").replace(">", "&gt;")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": PROMPTS["describe_document"].format(text=text)},
    ]


def correction_message(failures: dict[str, str]) -> Message:
    lines = "\n".join(f"- {name}: {reason}" for name, reason in failures.items())
    return {"role": "user", "content": PROMPTS["correct_fields"].format(failures=lines)}
