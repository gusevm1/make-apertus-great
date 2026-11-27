from uuid import UUID

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
