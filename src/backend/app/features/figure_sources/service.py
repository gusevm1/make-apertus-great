from typing import Any

from app.core.provenance import FigureRow, FigureSource
from app.features.documents.schemas import Document
from app.features.figure_checks.service import Figure, FigureCheckService
from app.features.ledger.service import LedgerService
from app.features.tool_calls.schemas import ToolCall

# The card under a figure lists this many records; `count` says how many there are.
ROWS_MAX = 5
# Keys whose values name something; a number in them is never a figure.
_REFERENCE_KEYS = {"id", "ids", "row_ids", "booking_ids", "iban", "url", "language"}

Path = tuple[dict[str, Any], ...]


class FigureSourceService:
    def __init__(
        self, figure_checks: FigureCheckService, ledger: LedgerService, token: str
    ) -> None:
        self.figure_checks = figure_checks
        self.ledger = ledger
        self.token = token

    async def figure_sources(
        self, answer: str, calls: list[ToolCall], documents: list[Document]
    ) -> list[FigureSource]:
        """For each figure of the answer, the tool result, page or document that holds it."""
        sources: dict[str, FigureSource] = {}
        for figure in self.figure_checks.figures(answer=answer):
            if figure.text in sources:
                continue
            source = await self._source(figure=figure, calls=calls, documents=documents)
            if source is not None:
                sources[figure.text] = source
        return list(sources.values())

    async def _source(
        self, figure: Figure, calls: list[ToolCall], documents: list[Document]
    ) -> FigureSource | None:
        # The newest result first: a follow-up's figure comes from the call made for it.
        for call in reversed(calls):
            if call.result is None:
                continue
            path = self._best_path(figure=figure, value=call.result)
            if path is not None:
                return await self._from_call(
                    figure=figure, call=call, result=call.result, path=path
                )
        for document in documents:
            if self.figure_checks.is_in(figure=figure, text=document.markdown):
                return FigureSource(text=figure.text, label=document.name)
        return None

    # A number beats a sentence that repeats it, and the deepest number names its own row.
    def _best_path(self, figure: Figure, value: Any) -> Path | None:
        hits = list(self._hits(figure=figure, value=value, parents=()))
        if not hits:
            return None
        return max(hits, key=lambda hit: (hit[0], len(hit[1])))[1]

    def _hits(self, figure: Figure, value: Any, parents: Path) -> Any:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _REFERENCE_KEYS or key.endswith("_id"):
                    continue
                yield from self._hits(figure=figure, value=item, parents=(*parents, value))
            return
        if isinstance(value, list):
            for item in value:
                yield from self._hits(figure=figure, value=item, parents=parents)
            return
        if value is None or isinstance(value, bool):
            return
        if self.figure_checks.is_in(figure=figure, text=str(value)):
            yield (not isinstance(value, str) or _is_number(text=value), parents)

    async def _from_call(
        self, figure: Figure, call: ToolCall, result: dict[str, Any], path: Path
    ) -> FigureSource:
        page = next((part for part in reversed(path) if isinstance(part.get("url"), str)), None)
        if page is not None:
            return FigureSource(
                text=figure.text,
                label=str(page.get("title") or call.title),
                tool_call_id=str(call.id),
                url=page["url"],
            )
        record = next((part for part in reversed(path) if _is_record(value=part)), None)
        if record is not None:
            return FigureSource(
                text=figure.text,
                label=call.title,
                tool_call_id=str(call.id),
                rows=[_row_of(record=record)],
                count=1,
            )
        ids, group = _booking_ids(result=result, path=path)
        rows = await self._rows(ids=ids[:ROWS_MAX], result=result)
        return FigureSource(
            text=figure.text,
            label=call.title if group is None else f"{call.title}, {group}",
            tool_call_id=str(call.id),
            rows=rows,
            count=len(ids),
        )

    async def _rows(self, ids: list[str], result: dict[str, Any]) -> list[FigureRow]:
        if not ids:
            return []
        records = {str(record["id"]): record for record in _records(value=result)}
        found = {row_id: _row_of(record=records[row_id]) for row_id in ids if row_id in records}
        if len(found) < len(ids):
            for row in await self.ledger.list_rows(token=self.token):
                if row.id in ids and row.id not in found:
                    found[row.id] = FigureRow(
                        id=row.id,
                        date=row.date.isoformat(),
                        text=row.text,
                        amount_chf=str(row.amount_chf),
                    )
        return [found[row_id] for row_id in ids if row_id in found]


def _is_number(text: str) -> bool:
    return text.replace(".", "", 1).replace("-", "", 1).isdigit()


def _is_record(value: dict[str, Any]) -> bool:
    return isinstance(value.get("id"), str) and "amount_chf" in value


def _row_of(record: dict[str, Any]) -> FigureRow:
    day = record.get("date") or record.get("due")
    text = record.get("text") or record.get("payee") or record.get("counterparty")
    amount = record.get("amount_chf")
    return FigureRow(
        id=str(record["id"]),
        date=None if day is None else str(day),
        text=str(text or record["id"]),
        amount_chf=None if amount is None else str(amount),
    )


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [record for item in value for record in _records(value=item)]
    if not isinstance(value, dict):
        return []
    own = [value] if _is_record(value=value) else []
    return own + [record for item in value.values() for record in _records(value=item)]


# A result names the bookings of its rows in `row_ids`, keyed by the row's month or name.
def _booking_ids(result: dict[str, Any], path: Path) -> tuple[list[str], str | None]:
    row_ids = result.get("row_ids")
    if isinstance(row_ids, list):
        return [str(row_id) for row_id in row_ids], None
    if not isinstance(row_ids, dict):
        return [], None
    for part in reversed(path[1:]):
        for value in part.values():
            if isinstance(value, str) and value in row_ids:
                return _flat_ids(value=row_ids[value]), value
    return _flat_ids(value=row_ids), None


def _flat_ids(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [row_id for item in value.values() for row_id in _flat_ids(value=item)]
    if isinstance(value, list):
        return list(dict.fromkeys(str(row_id) for row_id in value))
    return []
