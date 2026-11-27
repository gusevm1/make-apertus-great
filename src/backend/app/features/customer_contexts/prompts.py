from typing import Any

from app.core.prompts import load_prompts
from app.features.context_entries.schemas import ContextEntry
from app.features.documents.schemas import Document, DocumentField

PROMPTS = load_prompts(prompts_py=__file__)
BLOCK_MAX_CHARS = 6000
# What the chat may know from /customer; address, email, mobile and advisor stay out.
PROFILE_FIELDS = (
    "birth_date",
    "civil_status",
    "partner_name",
    "occupation",
    "employer",
    "gross_salary_chf",
    "salary_payments_per_year",
    "health_insurance",
    "savings_goal",
    "risk_profile",
    "children",
    "property",
)


def customer_block(
    profile: dict[str, Any], documents: list[Document], entries: list[ContextEntry]
) -> str:
    """The customer block for a turn; `documents` and `entries` newest first."""
    documents, entries = list(documents), list(entries)
    left_out_documents, left_out_entries = 0, 0
    while True:
        block = PROMPTS["customer"].format(
            profile=_lines(lines=_profile_lines(profile=profile), left_out=0),
            documents=_lines(
                lines=[_document_line(document=document) for document in documents],
                left_out=left_out_documents,
            ),
            entries=_lines(
                lines=[_entry_line(entry=entry) for entry in entries], left_out=left_out_entries
            ),
        )
        if len(block) <= BLOCK_MAX_CHARS or (not documents and not entries):
            return block
        # The oldest documents go first, then the oldest entries.
        if documents:
            documents.pop()
            left_out_documents += 1
        else:
            entries.pop()
            left_out_entries += 1


def _lines(lines: list[str], left_out: int) -> str:
    if left_out > 0:
        lines = [*lines, PROMPTS["left_out"].format(count=left_out)]
    if not lines:
        return PROMPTS["none"]
    return "\n".join(lines)


def _profile_lines(profile: dict[str, Any]) -> list[str]:
    name = " ".join(
        str(profile[key]) for key in ("first_name", "last_name") if profile.get(key) is not None
    )
    values = {"name": name, **{key: profile.get(key) for key in PROFILE_FIELDS}}
    return [
        f"- {key}: {_clean(text=str(value))}"
        for key, value in values.items()
        if value is not None and value != ""
    ]


def _document_line(document: Document) -> str:
    about = [
        _clean(text=str(value))
        for value in (document.title, document.kind, document.document_date)
        if value is not None
    ]
    parts = [", ".join(about)] if about else []
    parts += [_field(field=field) for field in document.fields]
    line = f"- {_clean(text=document.name)}"
    return line if not parts else f"{line}: " + "; ".join(parts)


def _field(field: DocumentField) -> str:
    amount = None if field.amount is None else f"{field.amount} {field.currency or ''}".strip()
    value = " ".join(
        _clean(text=str(part)) for part in (amount, field.date, field.text) if part is not None
    )
    return PROMPTS["field_passage"].format(
        name=field.name, value=value, passage=_clean(text=field.passage)
    )


def _entry_line(entry: ContextEntry) -> str:
    parts = [_clean(text=entry.text)]
    if entry.amount_chf is not None:
        parts.append(PROMPTS["entry_amount"].format(amount=entry.amount_chf))
    if entry.target_date is not None:
        parts.append(PROMPTS["entry_date"].format(date=entry.target_date))
    return f"- {entry.kind}: " + "; ".join(parts)


def _clean(text: str) -> str:
    # On one line and escaped, a value can neither start a section nor close the block.
    return " ".join(text.split()).replace("<", "&lt;").replace(">", "&gt;")
