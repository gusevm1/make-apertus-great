from app.clients.apertus import Message
from app.core.prompts import load_prompts
from app.features.documents.schemas import FIELD_NAMES, Document, DocumentKind

PROMPTS = load_prompts(prompts_py=__file__)


def describe_prompt(markdown: str) -> list[Message]:
    field_names = "\n".join(
        f"  - {kind}: {', '.join(names)}" for kind, names in FIELD_NAMES.items()
    )
    system = PROMPTS["describe_system"].format(
        kinds=", ".join(DocumentKind.__args__), field_names=field_names
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": PROMPTS["describe_document"].format(text=escaped(text=markdown)),
        },
    ]


def read_prompt(documents: list[Document], question: str) -> list[Message]:
    blocks = "".join(
        PROMPTS["read_document_text"].format(
            name=escaped(text=document.name).replace('"', "&quot;"),
            text=escaped(text=document.markdown),
        )
        for document in documents
    )
    content = blocks + PROMPTS["read_question"].format(question=escaped(text=question))
    return [
        {"role": "system", "content": PROMPTS["read_system"]},
        {"role": "user", "content": content},
    ]


def passages_correction_message(failures: list[str]) -> Message:
    lines = "\n".join(f"- {failure}" for failure in failures)
    return {"role": "user", "content": PROMPTS["correct_passages"].format(failures=lines)}


def escaped(text: str) -> str:
    # Escaped, a text can neither close its block nor open a tag of its own.
    return text.replace("<", "&lt;").replace(">", "&gt;")


def correction_message(failures: dict[str, str]) -> Message:
    lines = "\n".join(f"- {name}: {reason}" for name, reason in failures.items())
    return {"role": "user", "content": PROMPTS["correct_fields"].format(failures=lines)}
