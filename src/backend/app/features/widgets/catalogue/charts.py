import json
from functools import cache
from typing import Any

import vl_convert

from app.core.errors import BadRequestError
from app.features.widgets.catalogue.schemas import BarChart, LineChart
from app.features.widgets.catalogue.values import display, is_number, rows, short

VEGA_LITE_VERSION = "5.21"
# The width a static chart is drawn at; the page scales its SVG to the tile.
STATIC_WIDTH = 520
BAR_HEIGHT = 230
LINE_HEIGHT = 220
ROW_HEIGHT = 28
LABEL_LIMIT = 160
FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
ACCENT = "#2e6b66"
ACCENT_LIGHT = "#cfe2df"
ACCENT_MID = "#5f9c95"
TEXT = "#12202a"
MUTED = "#5b6870"
GRID = "#e6e8e8"
SERIES = [ACCENT, MUTED, "#9cc2be", "#7f9fb0", "#c2c8c8"]
GLOBALS = "window.vegaEmbed = vegaEmbed; window.vega = vega; window.vegaLite = vegaLite;"
LOCALE = {"decimal": ".", "thousands": "'", "grouping": [3], "currency": ["CHF ", ""]}
THEME: dict[str, Any] = {
    "background": None,
    "font": FONT,
    "padding": {"left": 0, "right": 4, "top": 10, "bottom": 0},
    "view": {"stroke": None},
    "axis": {
        "labelColor": MUTED,
        "labelFontSize": 12,
        "labelPadding": 6,
        "domain": False,
        "ticks": False,
        "title": None,
        "gridColor": GRID,
    },
    "axisX": {"grid": False, "labelAngle": 0},
    "axisY": {"tickCount": 4, "labelFontWeight": 500},
    "legend": {
        "orient": "top",
        "direction": "horizontal",
        "title": None,
        "labelColor": TEXT,
        "labelFontSize": 12,
        "symbolType": "circle",
    },
}


def chart_spec(component: BarChart | LineChart, data: dict[str, Any], live: bool) -> dict[str, Any]:
    """The Vega-Lite spec of a chart, with its rows taken from DATA; it computes no figure."""
    fields = [component.x, component.y]
    if isinstance(component, LineChart) and component.series is not None:
        fields.append(component.series)
    found = rows(path=component.data, data=data, fields=fields)
    series = [None if len(fields) < 3 else str(row[fields[2]]) for row in found]
    seen: set[tuple[str | None, str]] = set()
    for index, row in enumerate(found):
        key = (series[index], str(row[component.x]))
        # Vega-Lite would draw the sum of two rows with one label, a figure DATA doesn't hold.
        if key in seen:
            raise BadRequestError(
                f"{component.data}[{index}] repeats {component.x} {key[1]}: a chart shows one "
                "value per label"
            )
        seen.add(key)
        if not is_number(value=row[component.y]):
            raise BadRequestError(f"{component.data}[{index}].{component.y} is not a number")
    shorts = [short(field=component.x, value=row[component.x]) for row in found]
    # Two rows of one series with the same short label ("Oct" of two years) get the full one.
    is_unique = len(set(zip(series, shorts, strict=True))) == len(found)
    values = []
    for index, row in enumerate(found):
        full = display(field=component.x, value=row[component.x])
        shown = display(field=component.y, value=row[component.y])
        path = f"{component.data}[{index}]"
        values.append(
            {
                "key": str(row[component.x]),
                "label": shorts[index] if is_unique else full,
                "y": row[component.y],
                "shown": shown,
                "series": series[index],
                "path": path,
                # What a screen reader says for the mark; the bridge reads the path in brackets.
                "description": f"{full}, {shown} ({path})",
                "booking_ids": row.get("booking_ids", []),
            }
        )
    # A horizontal chart's labels sit beside the plot, so its static plot is narrower.
    labels_beside = isinstance(component, BarChart) and component.horizontal
    size: dict[str, Any] = (
        {"width": "container", "autosize": {"type": "fit-x", "contains": "padding"}}
        if live
        else {"width": STATIC_WIDTH - LABEL_LIMIT if labels_beside else STATIC_WIDTH}
    )
    if isinstance(component, BarChart):
        return {**size, **_bar(component=component, values=values)}
    return {**size, **_line(values=values, has_series=len(fields) == 3)}


def static_svg(spec: dict[str, Any]) -> str:
    return vl_convert.vegalite_to_svg(
        vl_spec=spec, vl_version=VEGA_LITE_VERSION, config=THEME, format_locale=LOCALE
    )


@cache
def runtime() -> str:
    """Vega, Vega-Lite and Vega-Embed as one script, so a live page needs no network."""
    return vl_convert.javascript_bundle(snippet=GLOBALS, vl_version=VEGA_LITE_VERSION)


def _tooltip(y_title: str) -> list[dict[str, str]]:
    return [{"field": "label", "title": " "}, {"field": "shown", "title": y_title}]


def _bar(component: BarChart, values: list[dict[str, Any]]) -> dict[str, Any]:
    highlight = component.highlight
    accent = {
        "condition": {"test": f"datum.key === {_js(highlight)}", "value": ACCENT},
        "value": ACCENT_LIGHT if highlight is not None else ACCENT_MID,
    }
    text_colour = {
        "condition": {"test": f"datum.key === {_js(highlight)}", "value": TEXT},
        "value": MUTED,
    }
    label_axis = {"field": "label", "type": "ordinal", "sort": None}
    amount_axis = {"field": "y", "type": "quantitative", "stack": None, "axis": {"format": ",.0f"}}
    if component.horizontal:
        return {
            "height": {"step": ROW_HEIGHT},
            "padding": {"left": 0, "right": 56, "top": 4, "bottom": 0},
            "data": {"values": values},
            "encoding": {
                "y": {**label_axis, "axis": {"labelLimit": LABEL_LIMIT, "labelColor": TEXT}},
                "x": {"field": "y", "type": "quantitative", "stack": None, "axis": None},
                "description": {"field": "description"},
            },
            "layer": [
                {
                    "mark": {"type": "bar", "cornerRadiusEnd": 5, "height": {"band": 0.68}},
                    "encoding": {"color": accent, "tooltip": _tooltip(y_title=component.y)},
                },
                {
                    "mark": {
                        "type": "text",
                        "align": "left",
                        "dx": 6,
                        "fontSize": 12,
                        "fontWeight": 600,
                    },
                    "encoding": {"text": {"field": "y", "format": ",.0f"}, "color": text_colour},
                },
            ],
        }
    return {
        "height": BAR_HEIGHT,
        "data": {"values": values},
        "encoding": {"x": label_axis, "y": amount_axis, "description": {"field": "description"}},
        "layer": [
            {
                "mark": {
                    "type": "bar",
                    "cornerRadiusTopLeft": 7,
                    "cornerRadiusTopRight": 7,
                    "width": {"band": 0.62},
                },
                "encoding": {"color": accent, "tooltip": _tooltip(y_title=component.y)},
            },
            {
                "mark": {"type": "text", "dy": -9, "fontSize": 12, "fontWeight": 600},
                "encoding": {"text": {"field": "y", "format": ",.0f"}, "color": text_colour},
            },
        ],
    }


def _line(values: list[dict[str, Any]], has_series: bool) -> dict[str, Any]:
    encoding = {
        "x": {"field": "label", "type": "ordinal", "sort": None},
        "y": {"field": "y", "type": "quantitative", "stack": None, "axis": {"format": ",.0f"}},
    }
    # Only the points carry the row's path: on a line or area it would split the series.
    points = {
        "mark": {"type": "point", "filled": True, "size": 60},
        "encoding": {
            "description": {"field": "description"},
            "tooltip": [*_tooltip(y_title="value"), {"field": "series", "title": " "}],
        },
    }
    if has_series:
        colour = {"field": "series", "type": "nominal", "scale": {"range": SERIES}}
        return {
            "height": LINE_HEIGHT,
            "data": {"values": values},
            "encoding": {**encoding, "color": colour},
            "layer": [
                {"mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2.5}},
                points,
            ],
        }
    gradient = {
        "gradient": "linear",
        "x1": 1,
        "y1": 1,
        "x2": 1,
        "y2": 0,
        "stops": [{"offset": 0, "color": "#ffffff"}, {"offset": 1, "color": "#9cc2be"}],
    }
    return {
        "height": LINE_HEIGHT,
        "data": {"values": values},
        "encoding": encoding,
        "layer": [
            {
                "mark": {
                    "type": "area",
                    "interpolate": "monotone",
                    "color": gradient,
                    "line": {"color": ACCENT, "strokeWidth": 2.5},
                }
            },
            {**points, "mark": {**points["mark"], "color": ACCENT}},
        ],
    }


def _js(value: str | None) -> str:
    # A Vega expression literal; JSON quoting is valid there.
    return "null" if value is None else json.dumps(value)
