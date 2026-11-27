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
# A description of about 1300 tokens takes 50 s on a quiet gateway, past 60 s under load.
# Three attempts stay under the 300 s the page's proxy waits for an upload.
DESCRIBE_TIMEOUT_SECONDS = 90
READ_DOCUMENTS_MAX = 3
READ_FULL_TEXT_MAX_CHARS = 5_000
READ_MAX_CHARS = 300_000
READ_ANSWER_MAX_LENGTH = 1_500
READ_PASSAGES_MAX = 5
# Five passages and the answer keep a reading under the tool loop's 6000 characters.
READ_PASSAGE_MAX_LENGTH = 600
# The tool loop cuts a result at 6000 characters; the list stops earlier so its count fits.
LIST_MAX_CHARS = 5_000

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


# What the reader returns; all optional, so it never has to invent a value.
class ReaderPassage(BaseModel):
    document: str | None = None
    text: str | None = None


class ReaderAnswer(BaseModel):
    answer: str | None = None
    passages: list[ReaderPassage] = []


class DocumentText(BaseModel):
    name: str
    title: str | None
    text: str


class QuotedPassage(BaseModel):
    document: str
    text: str


# A short document comes back as `texts`; a long one as the reader's answer and passages.
class DocumentReading(BaseModel):
    texts: list[DocumentText] = []
    answer: str | None = None
    passages: list[QuotedPassage] = []
    provenance: Provenance | None = None


class DocumentSummary(BaseModel):
    name: str
    kind: DocumentKind | None
    title: str | None
    issuer: str | None
    document_date: date | None
    summary: str | None
    fields: list[DocumentField]
    created_at: datetime


# The newest documents that fit; `left_out` counts the older ones.
class DocumentList(BaseModel):
    documents: list[DocumentSummary]
    left_out: int
    # What the model reads when items are left out: how to search for them.
    note: str | None = None
