import json

from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts
from app.features.ledger.schemas import LedgerRow
from app.features.transaction_tags.schemas import CategoryCorrection, PersonalTag

PROMPTS = load_prompts(prompts_py=__file__)


def categorise_prompt(
    rows: dict[str, LedgerRow], examples: list[CategoryCorrection]
) -> list[LLMMessage]:
    """The batch for Apertus; `rows` are the ledger rows by their batch-local ref."""
    lines = "\n".join(_row_line(ref=ref, row=row) for ref, row in rows.items())
    # Escaped, a booking text can neither close the block nor open a tag of its own.
    lines = lines.replace("<", "&lt;").replace(">", "&gt;")
    system = PROMPTS["categorise_system"]
    if examples:
        corrections = "\n".join(
            json.dumps({"payee": example.payee, "category": example.category}, ensure_ascii=False)
            for example in examples
        )
        system += PROMPTS["categorise_examples"].format(corrections=_escape(text=corrections))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": PROMPTS["categorise_rows"].format(rows=lines)},
    ]


def _row_line(ref: str, row: LedgerRow) -> str:
    fields = {
        "ref": ref,
        "text": row.text,
        "counterparty": row.counterparty,
        "amount_chf": str(-row.amount_chf),
        "weekday": row.date.strftime("%A"),
        "channel": "credit card" if row.source == "card_transaction" else row.transaction_type,
        "original_amount": None if row.original_amount is None else str(abs(row.original_amount)),
        "original_currency": row.original_currency,
    }
    return json.dumps(
        {key: value for key, value in fields.items() if value is not None}, ensure_ascii=False
    )


def severity_prompt(
    account_names: list[str],
    transfer_texts: list[str],
    totals: dict[str, str],
    categories: list[str],
) -> list[LLMMessage]:
    """What Apertus sees of one customer, to rate the `categories` that have no severity yet."""
    # Escaped, an account name or transfer text can neither close a block nor open a tag.
    content = PROMPTS["severity_input"].format(
        accounts=_escape(text="\n".join(account_names)),
        transfers=_escape(text="\n".join(transfer_texts)),
        totals="\n".join(f"{category}: {total}" for category, total in totals.items()),
        categories="\n".join(categories),
    )
    return [
        {"role": "system", "content": PROMPTS["severity_system"]},
        {"role": "user", "content": content},
    ]


def _escape(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


def infer_tags_prompt(
    account_names: list[str],
    transfer_texts: list[str],
    spending: dict[str, list[str]],
    max_tags: int,
) -> list[LLMMessage]:
    """What Apertus sees of one customer, to propose at most `max_tags` personal tags."""
    content = PROMPTS["infer_tags_input"].format(
        accounts=_escape(text="\n".join(account_names)),
        transfers=_escape(text="\n".join(transfer_texts)),
        spending=_escape(
            text="\n".join(
                f"{category}: {', '.join(payees)}" for category, payees in spending.items()
            )
        ),
    )
    return [
        {"role": "system", "content": PROMPTS["infer_tags_system"].format(max_tags=max_tags)},
        {"role": "user", "content": content},
    ]


def assign_tags_prompt(
    tags: list[PersonalTag], rows: dict[str, LedgerRow], categories: dict[str, str]
) -> list[LLMMessage]:
    """The batch for Apertus; `rows` are the ledger rows by their batch-local ref."""
    tag_lines = "\n".join(
        json.dumps({"name": tag.name, "description": tag.description}, ensure_ascii=False)
        for tag in tags
    )
    row_lines = "\n".join(
        _assigned_row_line(ref=ref, row=row, category=categories.get(ref))
        for ref, row in rows.items()
    )
    content = PROMPTS["assign_tags_input"].format(
        tags=_escape(text=tag_lines), rows=_escape(text=row_lines)
    )
    return [
        {"role": "system", "content": PROMPTS["assign_tags_system"]},
        {"role": "user", "content": content},
    ]


def _assigned_row_line(ref: str, row: LedgerRow, category: str | None) -> str:
    fields = {
        "ref": ref,
        "kind": row.kind,
        "date": row.date.isoformat(),
        "text": row.text,
        "counterparty": row.counterparty,
        "category": category,
        "amount_chf": str(abs(row.amount_chf)),
        "original_amount": None if row.original_amount is None else str(abs(row.original_amount)),
        "original_currency": row.original_currency,
    }
    return json.dumps(
        {key: value for key, value in fields.items() if value is not None}, ensure_ascii=False
    )


def uncertain_pointer_line(count: int, language: str) -> str:
    """The line under an answer whose figure holds `count` bookings of uncertain category."""
    return PROMPTS[f"uncertain_pointer_{language}"].format(count=count)
