import json
import re
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.errors import BadRequestError
from app.features.widgets.catalogue.charts import LOCALE, THEME, chart_spec, runtime, static_svg
from app.features.widgets.catalogue.schemas import (
    FIELD_PATTERN,
    PATH_PATTERN,
    BarChart,
    Grid,
    ItemList,
    Kpi,
    LineChart,
    Node,
    Stack,
    StatRow,
    Table,
    WidgetSpec,
)
from app.features.widgets.catalogue.values import booking_ids, display, last_field, resolve, rows

Form = Literal["live", "static"]
TEMPLATES = Path(__file__).with_name("templates")
_CSP_REST = (
    "style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none'"
)
# Fetches, CDNs, forms and <base> are blocked; 'unsafe-eval' runs Vega's expressions in live pages.
CSP = {
    "static": f"default-src 'none'; script-src 'unsafe-inline'; {_CSP_REST}",
    "live": f"default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; {_CSP_REST}",
}
TABLE_ROWS = 50

_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["j2"]))
_css = (TEMPLATES / "widget.css").read_text(encoding="utf-8")
_bridge = (TEMPLATES / "bridge.js").read_text(encoding="utf-8")


def render(spec: WidgetSpec, data: dict[str, Any], form: Form) -> str:
    """The widget as one HTML page; `live` charts react in the browser, `static` ones are SVG."""
    charts: list[dict[str, Any]] = []
    body = _view(node=spec.body, data=data, form=form, charts=charts)
    payload = {"charts": charts, "config": THEME, "locale": LOCALE}
    return _env.get_template("page.html.j2").render(
        csp=CSP[form],
        css=_css,
        bridge=_bridge,
        title=spec.title,
        subtitle=spec.subtitle,
        body=body,
        form=form,
        components=_env.get_template("components.html.j2").module,
        runtime=runtime() if form == "live" else "",
        charts_json=_script_json(value=payload),
    )


def fallback(data: dict[str, Any]) -> WidgetSpec:
    """A plain widget built from DATA alone, for when no valid spec came back."""
    for key, value in data.items():
        if re.fullmatch(PATH_PATTERN, key) is None or not _is_rows(value=value):
            continue
        columns = [
            field
            for field, cell in value[0].items()
            if re.fullmatch(FIELD_PATTERN, field) is not None
            and not isinstance(cell, list | dict)
            and all(field in row for row in value)
        ]
        if len(columns) > 0:
            body = Table(type="table", rows=key, columns=columns[:5])
            return WidgetSpec(title=_title(field=key)[:80], body=body)
    for key, value in data.items():
        if re.fullmatch(PATH_PATTERN, key) is None:
            continue
        if isinstance(value, int | float) and not isinstance(value, bool):
            label = _title(field=key)[:80]
            return WidgetSpec(title=label, body=Kpi(type="kpi", label=label, value=key))
    raise BadRequestError("DATA holds no rows and no figure a widget can show")


def _is_rows(value: Any) -> bool:
    return (
        isinstance(value, list) and len(value) > 0 and all(isinstance(row, dict) for row in value)
    )


def _view(
    node: Node, data: dict[str, Any], form: Form, charts: list[dict[str, Any]]
) -> dict[str, Any]:
    if isinstance(node, Stack | Grid):
        children = [
            _view(node=child, data=data, form=form, charts=charts) for child in node.children
        ]
        columns = node.columns if isinstance(node, Grid) else None
        return {"type": node.type, "columns": columns, "children": children}
    if isinstance(node, Kpi):
        return _kpi(node=node, data=data)
    if isinstance(node, StatRow):
        stats = [_figure(path=stat.value, data=data) | {"label": stat.label} for stat in node.stats]
        return {"type": node.type, "stats": stats}
    if isinstance(node, Table):
        return _table(node=node, data=data)
    if isinstance(node, ItemList):
        return _list(node=node, data=data)
    return _chart(node=node, data=data, form=form, charts=charts)


def _figure(path: str, data: dict[str, Any]) -> dict[str, Any]:
    value = resolve(path=path, data=data)
    return {
        "path": path,
        "raw": json.dumps(value),
        "text": display(field=last_field(path=path), value=value),
        "booking_ids": json.dumps(booking_ids(path=path, data=data)),
    }


def _kpi(node: Kpi, data: dict[str, Any]) -> dict[str, Any]:
    view = {"type": node.type, "label": node.label, **_figure(path=node.value, data=data)}
    if node.compare is None:
        return view | {"compare_text": None}
    compare = _figure(path=node.compare, data=data)
    return view | {
        "compare_path": compare["path"],
        "compare_raw": compare["raw"],
        "compare_text": compare["text"],
        "compare_booking_ids": compare["booking_ids"],
        "compare_label": node.compare_label if node.compare_label is not None else "Compared with",
    }


def _table(node: Table, data: dict[str, Any]) -> dict[str, Any]:
    found = rows(path=node.rows, data=data, fields=node.columns)
    columns = [
        {
            "title": _title(field=field),
            "numeric": len(found) > 0 and isinstance(found[0][field], int | float),
            "date": field.endswith("date"),
        }
        for field in node.columns
    ]
    view_rows = [
        _row(path=f"{node.rows}[{index}]", row=row)
        | {"cells": [display(field=field, value=row[field]) for field in node.columns]}
        for index, row in enumerate(found[:TABLE_ROWS])
    ]
    view = {
        "type": node.type,
        "title": node.title,
        "path": node.rows,
        "columns": columns,
        "rows": view_rows,
        "cut_note": _cut_note(count=len(found)),
    }
    if node.total is None:
        return view | {"total": None}
    total = _figure(path=node.total, data=data)
    holder = node.total_column()
    label_at = next((index for index, field in enumerate(node.columns) if field != holder), None)
    cells = [
        {
            "text": total["text"] if field == holder else ("Total" if index == label_at else ""),
            "numeric": columns[index]["numeric"],
        }
        for index, field in enumerate(node.columns)
    ]
    if label_at is None:
        cells[0]["text"] = f"Total {total['text']}"
    return view | {"total": total | {"cells": cells}}


def _cut_note(count: int) -> str | None:
    return None if count <= TABLE_ROWS else f"First {TABLE_ROWS} of {count} rows"


def _list(node: ItemList, data: dict[str, Any]) -> dict[str, Any]:
    fields = [node.label, node.value] + ([node.detail] if node.detail is not None else [])
    found = rows(path=node.rows, data=data, fields=fields)
    items = [
        _row(path=f"{node.rows}[{index}]", row=row)
        | {
            "label": display(field=node.label, value=row[node.label]),
            "value": display(field=node.value, value=row[node.value]),
            "detail": None
            if node.detail is None
            else display(field=node.detail, value=row[node.detail]),
        }
        for index, row in enumerate(found[:TABLE_ROWS])
    ]
    return {
        "type": node.type,
        "title": node.title,
        "path": node.rows,
        "entries": items,
        "cut_note": _cut_note(count=len(found)),
    }


def _chart(
    node: BarChart | LineChart, data: dict[str, Any], form: Form, charts: list[dict[str, Any]]
) -> dict[str, Any]:
    chart_id = f"chart-{len(charts) + 1}"
    spec = chart_spec(component=node, data=data, live=form == "live")
    charts.append({"id": chart_id, "spec": spec})
    svg = static_svg(spec=spec) if form == "static" else None
    return {"type": node.type, "title": node.title, "path": node.data, "id": chart_id, "svg": svg}


def _row(path: str, row: dict[str, Any]) -> dict[str, Any]:
    shown = {field: value for field, value in row.items() if field != "booking_ids"}
    return {
        "path": path,
        "row_values": json.dumps(shown, ensure_ascii=False),
        "booking_ids": json.dumps(row.get("booking_ids", [])),
    }


def _title(field: str) -> str:
    return field.removesuffix("_chf").replace("_", " ").capitalize()


def _script_json(value: Any) -> str:
    # Inside a <script>, "<" must not start a closing tag.
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")
