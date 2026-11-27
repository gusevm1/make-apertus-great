import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.errors import BadRequestError
from app.features.widgets.catalogue.charts import (
    LOCALE,
    THEME,
    chart_spec,
    runtime,
    static_svg,
)
from app.features.widgets.catalogue.schemas import (
    FIELD_PATTERN,
    PATH_PATTERN,
    Callout,
    Chart,
    Donut,
    Grid,
    ItemList,
    Kpi,
    Node,
    Progress,
    Stack,
    Stat,
    StatRow,
    Table,
    Timeline,
    Trend,
    WidgetSpec,
)
from app.features.widgets.catalogue.values import (
    booking_ids,
    display,
    figure,
    is_date,
    is_number,
    last_field,
    rows,
)

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
# Half a Rappen: a total may differ from the sum of its rows by rounding only.
TOTAL_TOLERANCE = Decimal("0.005")

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
        return _kpi(node=node, data=data, form=form, charts=charts)
    if isinstance(node, StatRow):
        stats = [
            _figure(path=stat.value, data=data)
            | {"label": stat.label}
            | _trend_and_change(item=stat, data=data, form=form, charts=charts)
            for stat in node.stats
        ]
        return {"type": node.type, "stats": stats}
    if isinstance(node, Table):
        return _table(node=node, data=data)
    if isinstance(node, ItemList | Timeline):
        return _entries(node=node, data=data)
    if isinstance(node, Progress):
        return _progress(node=node, data=data)
    if isinstance(node, Callout):
        return {"type": node.type, "title": node.title, "text": node.text, "tone": node.tone}
    return _chart(node=node, data=data, form=form, charts=charts)


def _figure(path: str, data: dict[str, Any]) -> dict[str, Any]:
    value = figure(path=path, data=data)
    return {
        "path": path,
        "raw": json.dumps(value),
        "text": display(field=last_field(path=path), value=value),
        "booking_ids": json.dumps(booking_ids(path=path, data=data)),
    }


def _trend_and_change(
    item: Stat, data: dict[str, Any], form: Form, charts: list[dict[str, Any]]
) -> dict[str, Any]:
    trend = None
    if item.trend is not None:
        chart_id, svg, chart_rows, _ = _drawn(node=item.trend, data=data, form=form, charts=charts)
        trend = {"id": chart_id, "svg": svg, "rows": chart_rows, "path": item.trend.data}
    if item.change is None:
        return {"trend": trend, "change": None}
    value = figure(path=item.change, data=data)
    # The sign gives the direction; the figure shown is DATA's own, without its sign.
    direction = "up" if value > 0 else ("down" if value < 0 else None)
    is_good = direction == item.good_when
    change = _figure(path=item.change, data=data) | {
        "direction": direction,
        "tone": "neutral" if direction is None else ("good" if is_good else "bad"),
        "text": display(field=last_field(path=item.change), value=abs(value)),
        "word": {"up": "more", "down": "less", None: "no change"}[direction],
        "verdict": None if direction is None else ("good" if is_good else "to watch"),
    }
    return {"trend": trend, "change": change}


def _kpi(
    node: Kpi, data: dict[str, Any], form: Form, charts: list[dict[str, Any]]
) -> dict[str, Any]:
    view = {
        "type": node.type,
        "label": node.label,
        **_figure(path=node.value, data=data),
        **_trend_and_change(item=node, data=data, form=form, charts=charts),
    }
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
    _check_sum(
        total_path=node.total,
        rows_path=node.rows,
        column=holder,
        cells=[row[holder] for row in found] if holder is not None else [],
        total=figure(path=node.total, data=data),
    )
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


def _check_sum(
    total_path: str, rows_path: str, column: str | None, cells: list[Any], total: int | float
) -> None:
    """A total must be the sum of its column over all rows, not only those shown."""
    if not all(is_number(value=cell) for cell in cells):
        raise BadRequestError(f"{rows_path}: the {column} column holds no amounts for the total")
    column_sum = sum((Decimal(str(cell)) for cell in cells), Decimal(0))
    if abs(column_sum - Decimal(str(total))) > TOTAL_TOLERANCE:
        raise BadRequestError(
            f"{total_path} is {total}, but the {column} column of {rows_path} adds up to "
            f"{column_sum}"
        )


def _cut_note(count: int) -> str | None:
    return None if count <= TABLE_ROWS else f"First {TABLE_ROWS} of {count} rows"


def _entries(node: ItemList | Timeline, data: dict[str, Any]) -> dict[str, Any]:
    dated = isinstance(node, Timeline)
    fields = (
        ([node.date] if isinstance(node, Timeline) else [])
        + [node.label, node.value]
        + ([node.detail] if node.detail is not None else [])
    )
    found = rows(path=node.rows, data=data, fields=fields)
    if isinstance(node, Timeline):
        _check_dates(node=node, found=found)
    entries = [
        _row(path=f"{node.rows}[{index}]", row=row)
        | {
            "label": display(field=node.label, value=row[node.label]),
            "value": display(field=node.value, value=row[node.value]),
            "detail": None
            if node.detail is None
            else display(field=node.detail, value=row[node.detail]),
            "date": display(field=fields[0], value=row[fields[0]]) if dated else None,
        }
        for index, row in enumerate(found[:TABLE_ROWS])
    ]
    return {
        "type": node.type,
        "title": node.title,
        "path": node.rows,
        "entries": entries,
        "cut_note": _cut_note(count=len(found)),
    }


def _check_dates(node: Timeline, found: list[dict[str, Any]]) -> None:
    # A timeline shows its rows in DATA's order; it doesn't sort them, so they must be in order.
    previous = ""
    for index, row in enumerate(found):
        value = row[node.date]
        if not is_date(value=value):
            raise BadRequestError(f"{node.rows}[{index}].{node.date} is not a date: {value!r}")
        if value < previous:
            raise BadRequestError(
                f"{node.rows}[{index}].{node.date} comes before the row above it: a timeline "
                "needs its rows in date order"
            )
        previous = value


def _progress(node: Progress, data: dict[str, Any]) -> dict[str, Any]:
    value = figure(path=node.value, data=data)
    goal = figure(path=node.goal, data=data)
    if goal <= 0:
        raise BadRequestError(f"{node.goal} is {goal}: a goal must be above zero")
    # The bar's length only; no share of the goal is written as a figure.
    filled = min(max(Decimal(str(value)) / Decimal(str(goal)), Decimal(0)), Decimal(1))
    return {
        "type": node.type,
        "label": node.label,
        "value": _figure(path=node.value, data=data),
        "goal": _figure(path=node.goal, data=data),
        "goal_label": node.goal_label if node.goal_label is not None else "Goal",
        "fill": f"{filled * 100:.1f}",
    }


def _drawn(
    node: Chart | Trend, data: dict[str, Any], form: Form, charts: list[dict[str, Any]]
) -> tuple[str, str | None, str, dict[str, Any]]:
    chart_id = f"chart-{len(charts) + 1}"
    spec = chart_spec(component=node, data=data, live=form == "live")
    charts.append({"id": chart_id, "spec": spec})
    svg = static_svg(spec=spec) if form == "static" else None
    values = spec["data"]["values"]
    # A clicked mark names its row; the bridge looks up the row's figure and bookings here.
    chart_rows = {
        value["path"]: {
            "value": value["y"],
            "label": value["label"],
            "booking_ids": value["booking_ids"],
        }
        for value in values
    }
    return chart_id, svg, json.dumps(chart_rows, ensure_ascii=False), spec


def _chart(
    node: Chart, data: dict[str, Any], form: Form, charts: list[dict[str, Any]]
) -> dict[str, Any]:
    chart_id, svg, chart_rows, spec = _drawn(node=node, data=data, form=form, charts=charts)
    values = spec["data"]["values"]
    view = {
        "type": node.type,
        "title": node.title,
        "path": node.data,
        "id": chart_id,
        "svg": svg,
        "rows": chart_rows,
        "legend": None,
        "total": None,
    }
    if not isinstance(node, Donut):
        return view
    # The legend's swatches are the slices' own colours, the customer's where chosen.
    colours = spec["encoding"]["color"]["scale"]["range"]
    legend = [
        {
            "path": value["path"],
            "raw": json.dumps(value["y"]),
            "label": value["label"],
            "text": value["shown"],
            "booking_ids": json.dumps(value["booking_ids"]),
            "colour": colours[index],
        }
        for index, value in enumerate(values)
    ]
    if node.total is None:
        return view | {"legend": legend}
    _check_sum(
        total_path=node.total,
        rows_path=node.data,
        column=node.value,
        cells=[value["y"] for value in values],
        total=figure(path=node.total, data=data),
    )
    return view | {"legend": legend, "total": _figure(path=node.total, data=data)}


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
