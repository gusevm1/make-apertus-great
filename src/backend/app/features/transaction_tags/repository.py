from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.repository import BaseRepository
from app.features.transaction_tags.models import (
    CategorisationRunORM,
    CategoryCorrectionORM,
    CustomCategoryORM,
    PersonalTagAssignmentORM,
    PersonalTagEvaluationORM,
    PersonalTagORM,
    SeveritySettingORM,
    TransactionTagORM,
)
from app.features.transaction_tags.schemas import (
    CategorisationRun,
    CategoryCorrection,
    CustomCategory,
    PersonalTag,
    PersonalTagAssignment,
    PersonalTagEvaluation,
    SeveritySetting,
    TransactionTag,
)


class TransactionTagRepository(BaseRepository[TransactionTagORM, TransactionTag]):
    orm_model = TransactionTagORM
    schema = TransactionTag

    async def list_row_keys(self, owner_id: UUID) -> set[tuple[str, str]]:
        stmt = select(TransactionTagORM.row_source, TransactionTagORM.row_id).where(
            TransactionTagORM.owner_id == owner_id
        )
        rows = await self.session.execute(stmt)
        keys = {(row.row_source, row.row_id) for row in rows}
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return keys

    async def list_for_owner(self, owner_id: UUID) -> list[TransactionTag]:
        tags = await self.list(owner_id=owner_id)
        await self.session.commit()
        return tags

    async def list_categories(self, owner_id: UUID) -> dict[tuple[str, str], str]:
        """The category of every tagged row, by (row_source, row_id)."""
        stmt = select(
            TransactionTagORM.row_source, TransactionTagORM.row_id, TransactionTagORM.category
        ).where(TransactionTagORM.owner_id == owner_id)
        rows = await self.session.execute(stmt)
        categories = {(row.row_source, row.row_id): row.category for row in rows}
        await self.session.commit()
        return categories

    async def upsert_categories(self, values: list[dict[str, object]]) -> int:
        """Store a category on these rows, tagged already or not; returns the count."""
        if not values:
            return 0
        stmt = insert(TransactionTagORM).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["owner_id", "row_source", "row_id"],
            set_={
                "category": stmt.excluded.category,
                "category_set_by": stmt.excluded.category_set_by,
                "category_model": stmt.excluded.category_model,
                "category_confirmed": stmt.excluded.category_confirmed,
                "category_certainty": stmt.excluded.category_certainty,
                "category_alternative": stmt.excluded.category_alternative,
                "updated_at": func.now(),
            },
        ).returning(TransactionTagORM.id)
        changed = len((await self.session.scalars(stmt)).all())
        await self.session.commit()
        return changed

    async def replace_model_categories(self, values: list[dict[str, object]]) -> int:
        """Store Apertus's new answers, but never over a row the customer decided meanwhile."""
        if not values:
            return 0
        stmt = insert(TransactionTagORM).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["owner_id", "row_source", "row_id"],
            set_={
                "category": stmt.excluded.category,
                "category_model": stmt.excluded.category_model,
                "category_certainty": stmt.excluded.category_certainty,
                "category_alternative": stmt.excluded.category_alternative,
                "updated_at": func.now(),
            },
            where=TransactionTagORM.category_set_by == "model",
        ).returning(TransactionTagORM.id)
        changed = len((await self.session.scalars(stmt)).all())
        await self.session.commit()
        return changed

    async def create_many(self, values: list[dict[str, object]]) -> int:
        """Store tags, keeping rows that are tagged already; returns how many are new."""
        if not values:
            return 0
        stmt = (
            insert(TransactionTagORM)
            .values(values)
            .on_conflict_do_nothing(index_elements=["owner_id", "row_source", "row_id"])
            .returning(TransactionTagORM.id)
        )
        created = len((await self.session.scalars(stmt)).all())
        await self.session.commit()
        return created


class CategoryCorrectionRepository(BaseRepository[CategoryCorrectionORM, CategoryCorrection]):
    orm_model = CategoryCorrectionORM
    schema = CategoryCorrection
    sortable_fields = frozenset({"created_at", "updated_at"})

    async def list_newest(self, owner_id: UUID) -> list[CategoryCorrection]:
        corrections = await self.list(sort="-updated_at", owner_id=owner_id)
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return corrections

    async def upsert(self, owner_id: UUID, payee: str, category: str) -> None:
        stmt = (
            insert(CategoryCorrectionORM)
            .values(owner_id=owner_id, payee=payee, category=category)
            .on_conflict_do_update(
                index_elements=["owner_id", "payee"],
                set_={"category": category, "updated_at": func.now()},
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()


class CustomCategoryRepository(BaseRepository[CustomCategoryORM, CustomCategory]):
    orm_model = CustomCategoryORM
    schema = CustomCategory
    sortable_fields = frozenset({"created_at"})

    async def list_for_owner(self, owner_id: UUID) -> list[CustomCategory]:
        categories = await self.list(sort="created_at", owner_id=owner_id)
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return categories


class SeveritySettingRepository(BaseRepository[SeveritySettingORM, SeveritySetting]):
    orm_model = SeveritySettingORM
    schema = SeveritySetting

    async def list_for_owner(self, owner_id: UUID) -> list[SeveritySetting]:
        settings = await self.list(owner_id=owner_id)
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return settings

    async def create_missing(self, values: list[dict[str, object]]) -> None:
        """Store settings, keeping the ones that exist already."""
        if not values:
            return
        stmt = (
            insert(SeveritySettingORM)
            .values(values)
            .on_conflict_do_nothing(index_elements=["owner_id", "scope", "key"])
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def upsert(self, values: dict[str, object]) -> SeveritySetting:
        stmt = (
            insert(SeveritySettingORM)
            .values(values)
            .on_conflict_do_update(
                index_elements=["owner_id", "scope", "key"],
                set_={
                    "severity": values["severity"],
                    "set_by": values["set_by"],
                    "model": values["model"],
                    "confirmed": values["confirmed"],
                    "reason": values["reason"],
                    "updated_at": func.now(),
                },
            )
            .returning(SeveritySettingORM)
        )
        row = (await self.session.scalars(stmt)).one()
        setting = self._to_schema(row=row)
        await self.session.commit()
        return setting


class PersonalTagRepository(BaseRepository[PersonalTagORM, PersonalTag]):
    orm_model = PersonalTagORM
    schema = PersonalTag
    sortable_fields = frozenset({"created_at", "name"})

    async def get_owned(self, tag_id: UUID, owner_id: UUID) -> PersonalTag | None:
        stmt = select(PersonalTagORM).where(
            PersonalTagORM.id == tag_id, PersonalTagORM.owner_id == owner_id
        )
        row = await self.session.scalar(stmt)
        return None if row is None else self._to_schema(row=row)

    async def list_for_owner(self, owner_id: UUID) -> list[PersonalTag]:
        tags = await self.list(sort="name", owner_id=owner_id)
        # Ends the read's transaction, so none stays open while Apertus works.
        await self.session.commit()
        return tags

    async def name_taken(self, owner_id: UUID, name: str, except_id: UUID | None = None) -> bool:
        stmt = select(PersonalTagORM.id).where(
            PersonalTagORM.owner_id == owner_id, func.lower(PersonalTagORM.name) == name.lower()
        )
        if except_id is not None:
            stmt = stmt.where(PersonalTagORM.id != except_id)
        taken = await self.session.scalar(stmt) is not None
        await self.session.commit()
        return taken

    async def create_missing(self, values: list[dict[str, object]]) -> None:
        """Store tags, keeping the ones whose name the customer has already."""
        if not values:
            return
        await self.session.execute(insert(PersonalTagORM).values(values).on_conflict_do_nothing())
        await self.session.commit()


class PersonalTagAssignmentRepository(
    BaseRepository[PersonalTagAssignmentORM, PersonalTagAssignment]
):
    orm_model = PersonalTagAssignmentORM
    schema = PersonalTagAssignment

    async def list_for_owner(self, owner_id: UUID) -> list[PersonalTagAssignment]:
        assignments = await self.list(owner_id=owner_id)
        await self.session.commit()
        return assignments

    async def list_for_tag(self, tag_id: UUID) -> list[PersonalTagAssignment]:
        assignments = await self.list(tag_id=tag_id)
        await self.session.commit()
        return assignments

    async def create_missing(self, values: list[dict[str, object]]) -> list[PersonalTagAssignment]:
        """Store assignments, keeping the ones that exist already; returns the new ones."""
        if not values:
            return []
        stmt = (
            insert(PersonalTagAssignmentORM)
            .values(values)
            .on_conflict_do_nothing(index_elements=["tag_id", "row_source", "row_id"])
            .returning(PersonalTagAssignmentORM)
        )
        created = [self._to_schema(row=row) for row in await self.session.scalars(stmt)]
        await self.session.commit()
        return created

    async def delete_in_tag(self, assignment_id: UUID, tag_id: UUID) -> bool:
        stmt = (
            delete(PersonalTagAssignmentORM)
            .where(
                PersonalTagAssignmentORM.id == assignment_id,
                PersonalTagAssignmentORM.tag_id == tag_id,
            )
            .returning(PersonalTagAssignmentORM.id)
        )
        deleted = await self.session.scalar(stmt) is not None
        await self.session.commit()
        return deleted


class PersonalTagEvaluationRepository(
    BaseRepository[PersonalTagEvaluationORM, PersonalTagEvaluation]
):
    orm_model = PersonalTagEvaluationORM
    schema = PersonalTagEvaluation

    async def delete_for_owner(self, owner_id: UUID) -> None:
        """Forget which rows were judged, so the next run judges them against every tag."""
        await self.session.execute(
            delete(PersonalTagEvaluationORM).where(PersonalTagEvaluationORM.owner_id == owner_id)
        )
        await self.session.commit()

    async def list_row_keys(self, owner_id: UUID) -> set[tuple[str, str]]:
        stmt = select(PersonalTagEvaluationORM.row_source, PersonalTagEvaluationORM.row_id).where(
            PersonalTagEvaluationORM.owner_id == owner_id
        )
        keys = {(row.row_source, row.row_id) for row in await self.session.execute(stmt)}
        await self.session.commit()
        return keys

    async def create_missing(self, values: list[dict[str, object]]) -> None:
        if not values:
            return
        stmt = (
            insert(PersonalTagEvaluationORM)
            .values(values)
            .on_conflict_do_nothing(index_elements=["owner_id", "row_source", "row_id"])
        )
        await self.session.execute(stmt)
        await self.session.commit()


class CategorisationRunRepository(BaseRepository[CategorisationRunORM, CategorisationRun]):
    orm_model = CategorisationRunORM
    schema = CategorisationRun
    sortable_fields = frozenset({"created_at"})

    async def list_for_owner(self, owner_id: UUID) -> list[CategorisationRun]:
        runs = await self.list(sort="-created_at", owner_id=owner_id)
        await self.session.commit()
        return runs

    async def get_owned(self, categorisation_id: UUID, owner_id: UUID) -> CategorisationRun | None:
        stmt = select(CategorisationRunORM).where(
            CategorisationRunORM.id == categorisation_id, CategorisationRunORM.owner_id == owner_id
        )
        row = await self.session.scalar(stmt)
        await self.session.commit()
        return None if row is None else self._to_schema(row=row)

    async def fail_unfinished(self, owner_id: UUID) -> None:
        """Close the runs of this customer that were queued or running."""
        stmt = (
            update(CategorisationRunORM)
            .where(
                CategorisationRunORM.owner_id == owner_id,
                CategorisationRunORM.status.in_(["queued", "running"]),
            )
            .values(status="failed", finished_at=func.now())
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def mark_running(self, run_id: UUID) -> None:
        stmt = (
            update(CategorisationRunORM)
            .where(CategorisationRunORM.id == run_id)
            .values(status="running", started_at=func.now())
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def mark_finished(
        self, run_id: UUID, status: str, counts: dict[str, int] | None = None
    ) -> None:
        stmt = (
            update(CategorisationRunORM)
            .where(CategorisationRunORM.id == run_id)
            .values(status=status, finished_at=func.now(), **(counts or {}))
        )
        await self.session.execute(stmt)
        await self.session.commit()
