import asyncio
import copy
import json
import re
import time
from typing import Any
from uuid import UUID

from app.clients.apertus import ApertusClient, Model
from app.core.errors import BadRequestError, NotFoundError, UpstreamError
from app.core.provenance import Check
from app.core.tools import TurnResult
from app.features.figure_checks.service import FigureCheckService
from app.features.widgets.catalogue.render import fallback, render
from app.features.widgets.catalogue.schemas import FIELD_PATTERN, WidgetSpec
from app.features.widgets.prompts import repair_messages, spec_messages
from app.features.widgets.repository import WidgetRepository, WidgetVersionRepository
from app.features.widgets.schemas import (
    PROMPTS,
    BuildWidgetArgs,
    BuiltWidget,
    Form,
    Widget,
    WidgetVersion,
)

BUILD_WIDGET = "build_widget"
SPEC_MODEL = Model.SMART
SPEC_PURPOSE = "widget_spec"
# Spec fields that hold the model's own words; the figure check reads them.
LABEL_FIELDS = {"title", "subtitle", "label", "compare_label", "goal_label", "text"}
# Tool results write amounts as decimal strings; the catalogue draws numbers only.
AMOUNT_SUFFIXES = ("_chf", "_percent", "_per_month")
_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")


class WidgetService:
    def __init__(
        self,
        widgets: WidgetRepository,
        versions: WidgetVersionRepository,
        apertus: ApertusClient,
        figure_checks: FigureCheckService,
    ) -> None:
        self.widgets = widgets
        self.versions = versions
        self.apertus = apertus
        self.figure_checks = figure_checks

    async def build_widget(
        self,
        owner_id: UUID,
        conversation_id: UUID,
        args: BuildWidgetArgs,
        results: list[TurnResult],
    ) -> BuiltWidget:
        """Draw the turn's earlier results as a widget and keep it as its first version."""
        used = [result for result in results if result.tool_name != BUILD_WIDGET]
        if len(used) == 0:
            raise BadRequestError(
                "No earlier tool call of this turn returned figures. List the tools that fetch "
                "them before build_widget."
            )
        data = widget_data(results=used)
        started = time.perf_counter()
        spec, model, check = await self._spec(request=args.request, data=data)
        checks = [check]
        figures = self.figure_checks.check_figures(
            answer="\n".join(_labels(value=spec.model_dump())),
            sources=[json.dumps(data, ensure_ascii=False), args.request],
        )
        if figures is not None:
            checks.append(figures)
        widget, version = await self.widgets.create_with_version(
            widget={
                "owner_id": owner_id,
                "conversation_id": conversation_id,
                "title": spec.title,
                "current_version": 1,
            },
            version={
                "number": 1,
                "spec": spec.model_dump(mode="json", exclude_defaults=True),
                "data": data,
                "request": args.request,
                "model": model,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "tool_call_ids": [str(result.tool_call_id) for result in used],
                "checks": [item.model_dump() for item in checks],
            },
        )
        return BuiltWidget(
            widget_id=widget.id,
            version_number=version.number,
            title=widget.title,
            note=PROMPTS["built_note"],
            checks=checks,
        )

    async def get_widget(self, widget_id: UUID, owner_id: UUID) -> Widget:
        """The customer's widget; another customer's is not found."""
        widget = await self.widgets.get_owned(widget_id=widget_id, owner_id=owner_id)
        if widget is None:
            raise NotFoundError(f"Widget {widget_id} not found")
        return widget

    async def render_version(
        self, widget: Widget, version_number: int, form: Form
    ) -> tuple[WidgetVersion, str]:
        """One version of a widget and its page, drawn from its stored spec and DATA."""
        version = await self.versions.get_number(widget_id=widget.id, number=version_number)
        if version is None:
            raise NotFoundError(f"Widget {widget.id} has no version {version_number}")
        spec = WidgetSpec.model_validate(version.spec)
        # Drawing charts is CPU work that would hold up every other request.
        html = await asyncio.to_thread(render, spec, version.data, form)
        return version, html

    async def _spec(
        self, request: str, data: dict[str, Any]
    ) -> tuple[WidgetSpec, str | None, Check]:
        messages = spec_messages(request=request, data=data)
        try:
            first = await self.apertus.structured(
                messages=messages, schema=WidgetSpec, model=SPEC_MODEL, purpose=SPEC_PURPOSE
            )
        except UpstreamError as exc:
            return _fallback(data=data, model=None, reason=exc.message)
        error = await _drawing_error(spec=first.content, data=data)
        if error is None:
            return (
                first.content,
                first.model,
                Check(name="widget_spec", passed=True, detail="first try"),
            )
        try:
            second = await self.apertus.structured(
                messages=repair_messages(messages=messages, spec=first.content, error=error),
                schema=WidgetSpec,
                model=SPEC_MODEL,
                purpose=SPEC_PURPOSE,
            )
        except UpstreamError as exc:
            return _fallback(data=data, model=first.model, reason=exc.message)
        error = await _drawing_error(spec=second.content, data=data)
        if error is None:
            check = Check(name="widget_spec", passed=True, detail="after one repair")
            return second.content, second.model, check
        return _fallback(data=data, model=second.model, reason=error)


def widget_data(results: list[TurnResult]) -> dict[str, Any]:
    # One flat DATA object for all results, with paths the catalogue can name.
    data: dict[str, Any] = {}
    for result in results:
        content = copy.deepcopy(result.result)
        row_ids = content.pop("row_ids", None)
        for key, value in content.items():
            if re.fullmatch(FIELD_PATTERN, key) is None:
                continue
            name = _free_name(data=data, wanted=key, prefix=result.tool_name)
            data[name] = _numbers(value=value, key=key)
            _attach_bookings(rows=data[name], row_ids=row_ids if isinstance(row_ids, dict) else {})
    for key in list(data):
        _hoist_nested(data=data, key=key)
    return data


async def _drawing_error(spec: WidgetSpec, data: dict[str, Any]) -> str | None:
    try:
        await asyncio.to_thread(render, spec, data, "live")
    except BadRequestError as exc:
        return exc.message
    return None


def _fallback(
    data: dict[str, Any], model: str | None, reason: str
) -> tuple[WidgetSpec, str | None, Check]:
    check = Check(name="widget_spec", passed=False, detail=f"plain widget instead: {reason}"[:300])
    return fallback(data=data), model, check


def _labels(value: Any, key: str = "") -> list[str]:
    if isinstance(value, dict):
        return [label for name, item in value.items() for label in _labels(value=item, key=name)]
    if isinstance(value, list):
        return [label for item in value for label in _labels(value=item, key=key)]
    return [value] if key in LABEL_FIELDS and isinstance(value, str) else []


def _free_name(data: dict[str, Any], wanted: str, prefix: str) -> str:
    if wanted not in data:
        return wanted
    name = f"{prefix}_{wanted}"
    number = 2
    while name in data:
        name = f"{prefix}_{wanted}_{number}"
        number += 1
    return name


def _numbers(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return {name: _numbers(value=item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        return [_numbers(value=item, key=key) for item in value]
    if isinstance(value, str) and key.endswith(AMOUNT_SUFFIXES) and _DECIMAL.match(value):
        value = float(value)
    # The ledger writes money out as negative; a field named money_out already says the direction.
    if (
        key.startswith("money_out")
        and isinstance(value, int | float)
        and not isinstance(value, bool)
    ):
        return abs(value)
    return value


def _attach_bookings(rows: Any, row_ids: dict[str, Any]) -> None:
    # A result names each row's bookings in `row_ids`, keyed by the row's month or name;
    # a listed booking is its own id.
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict) or "booking_ids" in row:
            continue
        key = next(
            (value for value in row.values() if isinstance(value, str) and value in row_ids), None
        )
        if key is not None:
            row["booking_ids"] = row_ids[key]
        elif isinstance(row.get("id"), str):
            row["booking_ids"] = [row["id"]]


def _hoist_nested(data: dict[str, Any], key: str) -> None:
    # The catalogue can't name rows inside rows, so a list in each row becomes a list of its own.
    rows = data[key]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return
    nested = {
        field
        for row in rows
        for field, value in row.items()
        if isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, dict) for item in value)
    }
    for field in sorted(nested):
        children = []
        for row in rows:
            parent = next((value for value in row.values() if isinstance(value, str)), None)
            children += [{"parent": parent, **child} for child in row.pop(field, [])]
        data[_free_name(data=data, wanted=f"{key}_{field}", prefix=key)] = children
