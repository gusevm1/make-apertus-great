import datetime as dt
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.provenance import Provenance

DOCUMENT_MAX_BYTES = 10 * 1024 * 1024
DOCUMENT_TOO_LARGE_MESSAGE = "The document is larger than 10 MB. Send a smaller one."
NAME_MAX_LENGTH = 200
# About 75k tokens, well inside the context the 70B model is given.
DESCRIBE_MAX_CHARS = 300_000
SUMMARY_MAX_LENGTH = 200

DocumentKind = Literal[
    "payslip",
    "pension_certificate",
    "insurance_policy",
    "contract",
    "offer",
    "invoice",
    "reminder",
    "statement",
    "other",
]
INVOICE_FIELDS = ("amount_due", "due_date", "payee", "iban", "reference")
FIELD_NAMES: dict[str, tuple[str, ...]] = {
    "payslip": ("month", "gross_pay", "net_pay"),
    "invoice": INVOICE_FIELDS,
    "reminder": INVOICE_FIELDS,
    "contract": ("monthly_amount", "start_date", "end_date", "notice_period"),
}


class DocumentField(BaseModel):
    name: str
    amount: float | None = None
    currency: str | None = None
    date: dt.date | None = None
    text: str | None = None
    # The words of the document the value was read from.
    passage: str


# Everything Apertus fills is optional, so a value the document lacks stays empty.
class DescribedField(BaseModel):
    name: str | None = None
    amount: float | None = None
    currency: str | None = None
    date: dt.date | None = None
    text: str | None = None
    passage: str | None = None


class DocumentDescription(BaseModel):
    kind: DocumentKind | None = None
    title: str | None = None
    issuer: str | None = None
    document_date: date | None = None
    summary: str | None = None
    fields: list[DescribedField] = []


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    banking_document_id: str
    name: str
    markdown: str
    created_at: datetime
    # Empty until Apertus has described the document.
    kind: DocumentKind | None = None
    title: str | None = None
    issuer: str | None = None
    document_date: date | None = None
    summary: str | None = None
    fields: list[DocumentField] = []
    provenance: Provenance | None = None


class ResponseDocument(BaseModel):
    id: UUID
    name: str
    kind: DocumentKind | None
    title: str | None
    issuer: str | None
    document_date: date | None
    summary: str | None
    fields: list[DocumentField]
    provenance: Provenance | None
    created_at: datetime
