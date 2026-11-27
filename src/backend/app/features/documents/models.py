from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DocumentORM(Base):
    __tablename__ = "documents"

    owner_id: Mapped[UUID] = mapped_column(index=True)
    # The file itself stays in the banking API's document store; this is its id there.
    banking_document_id: Mapped[str]
    name: Mapped[str]
    # Read once by the OCR service, so a question about the document never waits for it again.
    markdown: Mapped[str]
    # Apertus's description, read once on upload; empty when it could not describe the document.
    kind: Mapped[str | None]
    title: Mapped[str | None]
    issuer: Mapped[str | None]
    document_date: Mapped[date | None]
    summary: Mapped[str | None]
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
