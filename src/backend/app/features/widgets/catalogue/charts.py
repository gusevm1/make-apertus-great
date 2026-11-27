import json
import re
from functools import cache
from typing import Any

import vl_convert

from app.core.errors import BadRequestError
from app.features.widgets.catalogue.schemas import (
    AreaChart,
    BarChart,
    Chart,
    Comparison,
    Donut,
    Trend,
)
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
# Donut slices in order; a donut has at most one part per colour.
SLICES = [
    ACCENT,
    ACCENT_MID,
    "#9cc2be",
    ACCENT_LIGHT,
    "#7f9fb0",
    "#a9bfca",
    "#d0dde3",
    "#e3e9ea",
    "#c2c8c8",
]
# The colours a customer can choose, from the e-banking tokens; each is at least 3:1 on white.
PALETTE = {
    "petrol": ACCENT,
    "petrol_light": "#5f9c95",
    "navy": TEXT,
    "navy_light": "#4a6272",
    "grey": MUTED,
    "grey_light": "#8a959b",
    "red": "#b3261e",
    "red_light": "#e0464b",
    "green": "#1d7a45",
    "green_light": "#3d9a63",
    "blue": "#2f6fd6",
    "blue_light": "#5b8fe0",
    "amber": "#9a5b00",
    "amber_light": "#c27a12",
}
# A series value naming a year, month or day; the newest such series gets the accent colour.
PERIOD = re.compile(r"^\d{4}(-\d{2}){0,2}$")
# Earlier periods step back in lighter greys, so the current one stands out.
PERIOD_SERIES = [ACCENT, PALETTE["grey_light"], "#a9b2b6", "#c2c8c8"]
# A sparkline has one size in both forms, beside a figure.
SPARK_WIDTH = 160
SPARK_HEIGHT = 40
DONUT_SIZE = 220
DONUT_INNER = 66
DONUT_OUTER = 104
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


def chart_spec(component: Chart | Trend, data: dict[str, Any], live: bool) -> dict[str, Any]:
    """The Vega-Lite spec of a chart, with its rows taken from DATA; it computes no figure."""
    x_field, y_field, series_field = _fields(component=component)
    fields = [x_field, y_field] + ([series_field] if series_field is not None else [])
    found = rows(path=component.data, data=data, fields=fields)
    if isinstance(component, Donut) and len(found) > len(SLICES):
        raise BadRequestError(
            f"{component.data} has {len(found)} parts; a donut shows at most {len(SLICES)}"
        )
    series = [None if series_field is None else str(row[series_field]) for row in found]
    seen: set[tuple[str | None, str]] = set()
    for index, row in enumerate(found):
        key = (series[index], str(row[x_field]))
        # Vega-Lite would draw the sum of two rows with one label, a figure DATA doesn't hold.
        if key in seen:
            raise BadRequestError(
                f"{component.data}[{index}] repeats {x_field} {key[1]}: a chart shows one "
                "value per label"
            )
        seen.add(key)
        if not is_number(value=row[y_field]):
            raise BadRequestError(f"{component.data}[{index}].{y_field} is not a number")
        if isinstance(component, Donut) and row[y_field] < 0:
            raise BadRequestError(f"{component.data}[{index}].{y_field} is negative: no slice")
    shorts = [short(field=x_field, value=row[x_field]) for row in found]
    # Two rows of one series with the same short label ("Oct" of two years) get the full one.
    is_unique = len(set(zip(series, shorts, strict=True))) == len(found)
    values = []
    for index, row in enumerate(found):
        full = display(field=x_field, value=row[x_field])
        shown = display(field=y_field, value=row[y_field])
        path = f"{component.data}[{index}]"
        values.append(
            {
                "key": str(row[x_field]),
                "label": shorts[index] if is_unique else full,
                "y": row[y_field],
                "shown": shown,
                "series": series[index],
                "path": path,
                # What a screen reader says for the mark; the bridge reads the path in brackets.
                "description": f"{full}, {shown} ({path})",
                "booking_ids": row.get("booking_ids", []),
            }
        )
    if isinstance(component, Trend):
        return _sparkline(values=values)
    chosen = _chosen(component=component, values=values, has_series=series_field is not None)
    if isinstance(component, Donut):
        colours = [chosen.get(value["key"], SLICES[index]) for index, value in enumerate(values)]
        return _donut(values=values, colours=colours)
    # A horizontal chart's labels sit beside the plot, so its static plot is narrower.
    labels_beside = isinstance(component, BarChart) and component.horizontal
    size: dict[str, Any] = (
        {"width": "container", "autosize": {"type": "fit-x", "contains": "padding"}}
        if live
        else {"width": STATIC_WIDTH - LABEL_LIMIT if labels_beside else STATIC_WIDTH}
    )
    if isinstance(component, BarChart):
        return {**size, **_bar(component=component, values=values, chosen=chosen)}
    scale = _series_scale(series=[value["series"] for value in values], chosen=chosen)
    if isinstance(component, Comparison):
        return {**size, **_comparison(values=values, scale=scale)}
    has_series = series_field is not None
    filled = isinstance(component, AreaChart)
    return {**size, **_line(values=values, has_series=has_series, filled=filled, scale=scale)}


def _chosen(component: Chart, values: list[dict[str, Any]], has_series: bool) -> dict[str, str]:
    # The customer's colours by row label or series value; a key the chart lacks is refused.
    if component.colors is None:
        return {}
    keys = {value["series"] if has_series else value["key"] for value in values}
    for key in component.colors:
        if key not in keys:
            kind = "series value" if has_series else "label"
            raise BadRequestError(
                f"colors names {key!r}, which is no {kind} of {component.data}; "
                f"it has: {', '.join(sorted(str(each) for each in keys))}"
            )
    return {key: PALETTE[name] for key, name in component.colors.items()}


def _series_scale(series: list[str | None], chosen: dict[str, str]) -> dict[str, Any]:
    names = [name for name in dict.fromkeys(series) if name is not None]
    # Periods newest first, so the current year gets the accent colour and leads the legend.
    is_periods = len(names) > 0 and all(PERIOD.fullmatch(name) is not None for name in names)
    domain = sorted(names, reverse=is_periods)
    base = PERIOD_SERIES if is_periods else SERIES
    colours = [chosen.get(name, base[index % len(base)]) for index, name in enumerate(domain)]
    return {"domain": domain, "range": colours}


def _fields(component: Chart | Trend) -> tuple[str, str, str | None]:
    if isinstance(component, Donut):
        return component.label, component.value, None
    if isinstance(component, BarChart | Trend):
        return component.x, component.y, None
    return component.x, component.y, component.series


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


def _bar(
    component: BarChart, values: list[dict[str, Any]], chosen: dict[str, str]
) -> dict[str, Any]:
    highlight = component.highlight
    highlight_colour = (
        ACCENT if component.highlight_color is None else PALETTE[component.highlight_color]
    )
    # The customer's colours come first; keys are checked against the rows and JSON-quoted.
    conditions = [
        {"test": f"datum.key === {_js(key)}", "value": colour} for key, colour in chosen.items()
    ]
    conditions.append({"test": f"datum.key === {_js(highlight)}", "value": highlight_colour})
    accent = {
        "condition": conditions if len(conditions) > 1 else conditions[0],
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


def _line(
    values: list[dict[str, Any]], has_series: bool, filled: bool, scale: dict[str, Any]
) -> dict[str, Any]:
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
        colour = {"field": "series", "type": "nominal", "scale": scale}
        line = {"type": "line", "interpolate": "monotone", "strokeWidth": 2.5}
        # Areas overlap, never stack: a stacked area would draw sums DATA doesn't hold.
        shape = (
            {**line, "type": "area", "opacity": 0.22, "line": {"strokeWidth": 2.5}}
            if filled
            else line
        )
        if filled:
            # The legend shows the series colour, not the areas' transparency.
            colour = {**colour, "legend": {"symbolOpacity": 1}}
        return {
            "height": LINE_HEIGHT,
            "data": {"values": values},
            "encoding": {**encoding, "color": colour},
            "layer": [{"mark": shape}, points],
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


def _sparkline(values: list[dict[str, Any]]) -> dict[str, Any]:
    # No axes; every point is a click target, only the last one is drawn.
    marked = [{**value, "last": index == len(values) - 1} for index, value in enumerate(values)]
    return {
        "width": SPARK_WIDTH,
        "height": SPARK_HEIGHT,
        "padding": {"left": 2, "right": 6, "top": 6, "bottom": 6},
        "data": {"values": marked},
        "encoding": {
            # No padding at the ends, so the line starts where the figure above it starts.
            "x": {
                "field": "key",
                "type": "ordinal",
                "sort": None,
                "axis": None,
                "scale": {"padding": 0},
            },
            "y": {
                "field": "y",
                "type": "quantitative",
                "stack": None,
                "axis": None,
                "scale": {"zero": False},
            },
        },
        "layer": [
            {
                "mark": {
                    "type": "line",
                    "interpolate": "monotone",
                    "strokeWidth": 2,
                    "color": ACCENT,
                }
            },
            {
                "mark": {"type": "point", "filled": True, "size": 40, "color": ACCENT},
                "encoding": {
                    "opacity": {"condition": {"test": "datum.last", "value": 1}, "value": 0},
                    "description": {"field": "description"},
                    "tooltip": _tooltip(y_title="value"),
                },
            },
        ],
    }


def _comparison(values: list[dict[str, Any]], scale: dict[str, Any]) -> dict[str, Any]:
    # Bars of each series side by side per label; `stack: None` keeps every bar one row's value.
    return {
        "height": BAR_HEIGHT,
        "data": {"values": values},
        "encoding": {
            "x": {"field": "label", "type": "ordinal", "sort": None},
            "xOffset": {"field": "series", "type": "nominal"},
            "y": {"field": "y", "type": "quantitative", "stack": None, "axis": {"format": ",.0f"}},
            "color": {"field": "series", "type": "nominal", "scale": scale},
            "description": {"field": "description"},
        },
        "layer": [
            {
                "mark": {"type": "bar", "cornerRadiusTopLeft": 5, "cornerRadiusTopRight": 5},
                "encoding": {
                    "tooltip": [*_tooltip(y_title="value"), {"field": "series", "title": " "}]
                },
            }
        ],
    }


def _donut(values: list[dict[str, Any]], colours: list[str]) -> dict[str, Any]:
    ordered = [{**value, "order": index} for index, value in enumerate(values)]
    return {
        "width": DONUT_SIZE,
        "height": DONUT_SIZE,
        "data": {"values": ordered},
        "mark": {
            "type": "arc",
            "innerRadius": DONUT_INNER,
            "outerRadius": DONUT_OUTER,
            "padAngle": 0.012,
            "cornerRadius": 3,
        },
        "encoding": {
            # The angle has to stack to go round; no sum is drawn or written.
            "theta": {"field": "y", "type": "quantitative", "stack": True},
            "order": {"field": "order", "type": "quantitative"},
            "color": {
                "field": "path",
                "type": "nominal",
                "sort": None,
                "legend": None,
                "scale": {
                    "domain": [value["path"] for value in ordered],
                    "range": colours,
                },
            },
            "description": {"field": "description"},
            "tooltip": _tooltip(y_title="value"),
        },
    }


def _js(value: str | None) -> str:
    # A Vega expression literal; JSON quoting is valid there.
    return "null" if value is None else json.dumps(value)
