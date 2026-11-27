import re
from pathlib import Path
from typing import Any
from uuid import UUID

from app.clients.apertus import ApertusClient, Message, Model
from app.clients.banking import BankingClient
from app.clients.ocr import OcrClient
from app.core.errors import BadRequestError, NotFoundError, PayloadTooLargeError, UpstreamError
from app.core.provenance import Check, Provenance, Source
from app.features.documents.prompts import (
    correction_message,
    describe_prompt,
    passages_correction_message,
    read_prompt,
)
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import (
    DESCRIBE_MAX_CHARS,
    DOCUMENT_MAX_BYTES,
    DOCUMENT_TOO_LARGE_MESSAGE,
    FIELD_NAMES,
    LIST_MAX_CHARS,
    NAME_MAX_LENGTH,
    READ_ANSWER_MAX_LENGTH,
    READ_FULL_TEXT_MAX_CHARS,
    READ_MAX_CHARS,
    READ_PASSAGE_MAX_LENGTH,
    READ_PASSAGES_MAX,
    SUMMARY_MAX_LENGTH,
    DescribedField,
    Document,
    DocumentDescription,
    DocumentField,
    DocumentList,
    DocumentReading,
    DocumentSummary,
    DocumentText,
    QuotedPassage,
    ReaderAnswer,
)

# A table row in the OCR text reads "| Nettolohn | 8'742.35 |"; a passage may leave out the markup.
SPACE_AND_MARKUP = re.compile(r"[\s|*#]+")
SPACE_OR_MARKUP = r"[\s|*#]*"
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
PASSAGE_MISSING = "it has no passage"
VALUE_MISSING = "these words come without an amount, date or text"
PASSAGE_NOT_IN_TEXT = "these words are not in the document"
AMOUNT_NOT_IN_PASSAGE = "the amount is not in these words"
DOCUMENT_NOT_READ = "no document of this name was given"
PASSAGE_TOO_LONG = f"longer than {READ_PASSAGE_MAX_LENGTH} characters, quote fewer words"
# A failure quotes the start of its passage, so five of them keep the check short.
FAILURE_QUOTE_LENGTH = 80


class DocumentService:
    def __init__(
        self,
        documents: DocumentRepository,
        banking: BankingClient,
        ocr: OcrClient,
        apertus: ApertusClient,
    ) -> None:
        self.documents = documents
        self.banking = banking
        self.ocr = ocr
        self.apertus = apertus

    async def create_document(
        self, content: bytes, name: str | None, content_type: str | None, owner_id: UUID, token: str
    ) -> Document:
        """Read the upload once with OCR, store it in the e-banking, keep its text, describe it."""
        if len(content) > DOCUMENT_MAX_BYTES:
            raise PayloadTooLargeError(DOCUMENT_TOO_LARGE_MESSAGE)
        if not content:
            raise BadRequestError("The document is empty.")
        if not name:
            # The OCR service picks its reader from the file extension.
            raise BadRequestError("The document needs a file name with its extension.")
        name = name[-NAME_MAX_LENGTH:]
        # OCR first: a file it cannot read then leaves nothing behind in the e-banking.
        markdown = await self.ocr.convert(content=content, filename=name)
        stored = await self.banking.upload_document(
            token=token, content=content, filename=name, content_type=content_type
        )
        # Before the row is written, so no transaction is open during the model call.
        description = await self._describe(markdown=markdown)
        return await self.documents.create(
            owner_id=owner_id,
            banking_document_id=stored["id"],
            name=name,
            markdown=markdown,
            **description,
        )

    async def _describe(self, markdown: str) -> dict[str, Any]:
        text = markdown[:DESCRIBE_MAX_CHARS]
        messages = describe_prompt(markdown=text)
        try:
            result = await self.apertus.structured(
                messages=messages,
                schema=DocumentDescription,
                model=Model.SMART,
                purpose="describe_document",
            )
        except UpstreamError:
            # The upload stands without a description.
            return {}
        description = result.content
        fields, failures = checked_fields(description=description, text=text)
        latency_ms = result.latency_ms
        if failures:
            corrected, failures, correction_ms = await self._corrected(
                messages=messages, description=description, failures=failures, text=text
            )
            fields += corrected
            latency_ms += correction_ms
        return {
            "kind": description.kind,
            "title": description.title,
            "issuer": description.issuer,
            "document_date": description.document_date,
            "summary": _shortened(text=description.summary, max_length=SUMMARY_MAX_LENGTH),
            "fields": [field.model_dump(mode="json") for field in fields],
            "provenance": _provenance(
                model=result.model, latency_ms=latency_ms, failures=failures
            ).model_dump(),
        }

    async def _corrected(
        self,
        messages: list[Message],
        description: DocumentDescription,
        failures: dict[str, str],
        text: str,
    ) -> tuple[list[DocumentField], dict[str, str], int]:
        try:
            result = await self.apertus.structured(
                messages=[
                    *messages,
                    {"role": "assistant", "content": description.model_dump_json()},
                    correction_message(failures=failures),
                ],
                schema=DocumentDescription,
                model=Model.SMART,
                purpose="describe_document_correction",
            )
        except UpstreamError:
            return [], failures, 0
        retried = [field for field in result.content.fields if field.name in failures]
        corrected, failing_again = checked_fields(
            description=description.model_copy(update={"fields": retried}), text=text
        )
        passed = _names(fields=corrected)
        dropped = {
            name: failing_again.get(name, reason)
            for name, reason in failures.items()
            if name not in passed
        }
        return corrected, dropped, result.latency_ms

    async def read_documents(
        self, names: list[str], question: str, owner_id: UUID
    ) -> DocumentReading:
        """Short documents in full, longer ones as the reader's answer with checked passages."""
        # ponytail: loads every text of the customer; select by name once there are many
        owned = await self.documents.list_by_owner(owner_id=owner_id)
        documents = _resolved(names=names, documents=owned)
        length = sum(len(document.markdown) for document in documents)
        if length <= READ_FULL_TEXT_MAX_CHARS:
            texts = [
                DocumentText(name=document.name, title=document.title, text=document.markdown)
                for document in documents
            ]
            return DocumentReading(texts=texts)
        if length > READ_MAX_CHARS:
            raise BadRequestError(
                f"These documents have {length} characters together, more than the "
                f"{READ_MAX_CHARS} that can be read at once. Ask about fewer documents."
            )
        messages = read_prompt(documents=documents, question=question)
        result = await self.apertus.structured(
            messages=messages, schema=ReaderAnswer, model=Model.SMART, purpose="read_document"
        )
        reading, failures = checked_reading(answer=result.content, documents=documents)
        latency_ms = result.latency_ms
        if failures:
            corrected = await self.apertus.structured(
                messages=[
                    *messages,
                    {"role": "assistant", "content": result.content.model_dump_json()},
                    passages_correction_message(failures=failures),
                ],
                schema=ReaderAnswer,
                model=Model.SMART,
                purpose="read_document_correction",
            )
            reading, failures = checked_reading(answer=corrected.content, documents=documents)
            latency_ms += corrected.latency_ms
        detail = "; ".join(f"dropped {failure}" for failure in failures)
        provenance = Provenance(
            model=result.model,
            latency_ms=latency_ms,
            sources=[Source(id=str(document.id), title=document.name) for document in documents],
            checks=[Check(name="quotes_in_text", passed=not failures, detail=detail or None)],
        )
        return reading.model_copy(update={"provenance": provenance})

    async def list_documents(self, owner_id: UUID) -> list[Document]:
        """The customer's documents, newest first."""
        return await self.documents.list(owner_id=owner_id)

    async def list_summaries(self, owner_id: UUID, text: str | None) -> DocumentList:
        """The newest documents that fit, at least one, holding a word of `text` if given."""
        words = [] if text is None else text.split()
        documents = await self.documents.list_matching(owner_id=owner_id, words=words)
        summaries: list[DocumentSummary] = []
        used = 0
        for document in documents:
            summary = DocumentSummary.model_validate(document, from_attributes=True)
            used += len(summary.model_dump_json())
            if used > LIST_MAX_CHARS and summaries:
                break
            summaries.append(summary)
        return DocumentList(documents=summaries, left_out=len(documents) - len(summaries))

    async def delete_document(self, document: Document, token: str) -> None:
        """Remove the file from the e-banking, then our row with its text and description."""
        await self.banking.delete_document(token=token, document_id=document.banking_document_id)
        await self.documents.delete(entity_id=document.id)

    async def get_documents(self, document_ids: list[UUID], owner_id: UUID) -> list[Document]:
        """The customer's documents in the given order; someone else's counts as not found."""
        if not document_ids:
            return []
        found = await self.documents.list_owned(document_ids=document_ids, owner_id=owner_id)
        by_id = {document.id: document for document in found}
        missing = [str(document_id) for document_id in document_ids if document_id not in by_id]
        if missing:
            raise NotFoundError(f"Document not found: {', '.join(missing)}")
        return [by_id[document_id] for document_id in dict.fromkeys(document_ids)]


def checked_fields(
    description: DocumentDescription, text: str
) -> tuple[list[DocumentField], dict[str, str]]:
    allowed = FIELD_NAMES.get(description.kind or "other", ())
    passed: list[DocumentField] = []
    failures: dict[str, str] = {}
    for field in description.fields:
        name = field.name
        if name is None or name not in allowed or name in _names(fields=passed):
            continue
        passage = field.passage or ""
        if _squeezed(text=passage) == "" and not _has_value(field=field):
            # Apertus names a field the document does not state: it stays empty.
            continue
        reason = _failure(field=field, passage=passage, text=text)
        if reason is not None:
            failures.setdefault(name, reason)
            continue
        failures.pop(name, None)
        passed.append(_kept(field=field, name=name, passage=passage))
    return passed, failures


def checked_reading(
    answer: ReaderAnswer, documents: list[Document]
) -> tuple[DocumentReading, list[str]]:
    passages: list[QuotedPassage] = []
    failures: list[str] = []
    for passage in answer.passages:
        # Apertus saw the text with < and > escaped.
        text = (passage.text or "").replace("&lt;", "<").replace("&gt;", ">")
        squeezed = _squeezed(text=text)
        if squeezed == "" or len(passages) == READ_PASSAGES_MAX:
            continue
        document = _named(name=passage.document or "", documents=documents)
        if document is None:
            reason = DOCUMENT_NOT_READ
        elif len(text) > READ_PASSAGE_MAX_LENGTH:
            reason = PASSAGE_TOO_LONG
        elif not _in_text(squeezed=squeezed, text=document.markdown):
            reason = PASSAGE_NOT_IN_TEXT
        else:
            passages.append(QuotedPassage(document=document.name, text=text))
            continue
        quoted = _shortened(text=text, max_length=FAILURE_QUOTE_LENGTH)
        failures.append(f'"{quoted}" from {passage.document}: {reason}')
    reading = DocumentReading(
        answer=_shortened(text=answer.answer, max_length=READ_ANSWER_MAX_LENGTH),
        passages=passages,
    )
    return reading, failures


def _resolved(names: list[str], documents: list[Document]) -> list[Document]:
    found: dict[UUID, Document] = {}
    unknown: list[str] = []
    for name in names:
        document = _named(name=name, documents=documents)
        if document is None:
            unknown.append(name)
            continue
        found.setdefault(document.id, document)
    if unknown:
        listed = "; ".join(_listed(document=document) for document in documents) or "none"
        raise BadRequestError(
            f"Unknown document: {', '.join(unknown)}. "
            f"Name it by file name or title. The customer's documents: {listed}"
        )
    return list(found.values())


def _named(name: str, documents: list[Document]) -> Document | None:
    # The newest document with this file name, file name without extension, or title.
    key = name.strip().casefold()
    for document in documents:
        keys = {document.name.casefold(), Path(document.name).stem.casefold()}
        if document.title is not None:
            keys.add(document.title.casefold())
        if key in keys:
            return document
    return None


def _listed(document: Document) -> str:
    return document.name if document.title is None else f"{document.name} ({document.title})"


def _failure(field: DescribedField, passage: str, text: str) -> str | None:
    # Apertus saw the text with < and > escaped.
    squeezed = _squeezed(text=passage.replace("&lt;", "<").replace("&gt;", ">"))
    if squeezed == "":
        return PASSAGE_MISSING
    if not _has_value(field=field):
        reason = VALUE_MISSING
    elif not _in_text(squeezed=squeezed, text=text):
        reason = PASSAGE_NOT_IN_TEXT
    elif field.amount is not None and not _amount_in(amount=field.amount, passage=passage):
        reason = AMOUNT_NOT_IN_PASSAGE
    else:
        return None
    return f'"{passage}": {reason}'


def _in_text(squeezed: str, text: str) -> bool:
    # A number at either end of the passage has to be whole in the text, not cut short.
    pattern = SPACE_OR_MARKUP.join(re.escape(char) for char in squeezed)
    if squeezed[0].isdigit():
        pattern = r"(?<!\d)(?<!\d['.,])" + pattern
    if squeezed[-1].isdigit():
        pattern += r"(?!\d|['.,]\d)"
    return re.search(pattern, text) is not None


def _has_value(field: DescribedField) -> bool:
    return field.amount is not None or field.date is not None or field.text is not None


def _kept(field: DescribedField, name: str, passage: str) -> DocumentField:
    value = field.date
    if name == "month" and value is not None:
        value = value.replace(day=1)
    return DocumentField(
        name=name,
        amount=field.amount,
        currency=field.currency,
        date=value,
        text=field.text,
        passage=passage,
    )


def _squeezed(text: str) -> str:
    return SPACE_AND_MARKUP.sub("", text)


def _amount_in(amount: float, passage: str) -> bool:
    numbers = NUMBER.findall(passage.replace("'", "").replace("\u2019", ""))
    return any(abs(float(number.replace(",", ".")) - abs(amount)) < 0.005 for number in numbers)


def _names(fields: list[DocumentField]) -> set[str]:
    return {field.name for field in fields}


def _shortened(text: str | None, max_length: int) -> str | None:
    if text is None or len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _provenance(model: str, latency_ms: int, failures: dict[str, str]) -> Provenance:
    detail = "; ".join(f"dropped {name}: {reason}" for name, reason in failures.items())
    check = Check(name="fields_in_text", passed=not failures, detail=detail or None)
    return Provenance(model=model, latency_ms=latency_ms, checks=[check])
