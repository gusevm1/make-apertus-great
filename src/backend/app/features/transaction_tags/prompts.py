import json

from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts
from app.features.ledger.schemas import LedgerRow

PROMPTS = load_prompts(prompts_py=__file__)


def categorise_prompt(rows: dict[str, LedgerRow]) -> list[LLMMessage]:
    """The batch for Apertus; `rows` are the ledger rows by their batch-local ref."""
    lines = "\n".join(_row_line(ref=ref, row=row) for ref, row in rows.items())
    # Escaped, a booking text can neither close the block nor open a tag of its own.
    lines = lines.replace("<", "&lt;").replace(">", "&gt;")
    return [
        {"role": "system", "content": PROMPTS["categorise_system"]},
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
