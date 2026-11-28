import base64
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import vl_convert

from app.core.errors import BadRequestError
from app.features.widgets.catalogue.schemas import (
    AreaChart,
    BarChart,
    Calendar,
    Chart,
    Comparison,
    Donut,
    ForecastChart,
    LineChart,
    Trend,
    Waterfall,
)
from app.features.widgets.catalogue.values import (
    MONTHS,
    agree,
    display,
    figure,
    is_date,
    is_number,
    number,
    rows,
    short,
)

VEGA_LITE_VERSION = "5.21"
# The width a static chart is drawn at; the page scales its SVG to the tile.
STATIC_WIDTH = 520
BAR_HEIGHT = 230
LINE_HEIGHT = 220
ROW_HEIGHT = 28
LABEL_LIMIT = 160
# Half the width of a month label such as "Jan 2027", kept free right of a forecast's last point.
LAST_LABEL_ROOM = 30
FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
# Inter ships with the catalogue: vl-convert measures a label with the font the browser draws it in.
FONTS = Path(__file__).with_name("fonts")
FONT_WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
ACCENT = "#2e6b66"
ACCENT_LIGHT = "#cfe2df"
ACCENT_MID = "#5f9c95"
TEXT = "#12202a"
# The widget's background (tokens.css --surface): the fill of a hollow forecast point.
SURFACE = "#ffffff"
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
# Fields whose negative sign only says the money went out, such as amount_chf or money_out_chf.
OUTGOING = re.compile(r"amount|(^|_)out(_|$)")
PERIOD = re.compile(r"^\d{4}(-\d{2}){0,2}$")
# The newest period in the accent colour, earlier ones in quieter colours that are still 3:1 on
# white and never the accent again; a chart shows at most this many periods.
PERIOD_SERIES = [
    ACCENT,
    PALETTE["grey_light"],
    PALETTE["navy_light"],
    PALETTE["blue_light"],
    PALETTE["amber_light"],
]
# A falling waterfall step in grey; the total in navy.
STEP_DOWN = PALETTE["grey_light"]
# A day of the calendar is one cell; a calendar shows at most 53 Monday-to-Sunday columns.
CELL = 15
MAX_WEEKS = 53
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# A day without a row, and the scale from a little spending to the most; a square-root scale,
# so one large bill doesn't wash out every other day.
EMPTY_DAY = "#f2f3f3"
CALENDAR_RANGE = [ACCENT_LIGHT, ACCENT]
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


vl_convert.register_font_directory(str(FONTS))


def chart_spec(component: Chart | Trend, data: dict[str, Any], live: bool) -> dict[str, Any]:
    """The Vega-Lite spec of a chart, with its rows taken from DATA; it computes no figure."""
    x_field, y_field, series_field = _fields(component=component)
    fields = [x_field, y_field] + ([series_field] if series_field is not None else [])
    extra = _extra_fields(component=component)
    found = rows(path=component.data, data=data, fields=fields + extra)
    if isinstance(component, ForecastChart):
        _check_forecast(component=component, found=found)
    if isinstance(component, Calendar):
        _check_days(component=component, found=found)
    for index, row in enumerate(found):
        if not is_number(value=row[y_field]):
            raise BadRequestError(f"{component.data}[{index}].{y_field} is not a number")
    if isinstance(component, Waterfall):
        _check_steps(component=component, found=found)
    marks = _one_per_label(component=component, found=found, x_field=x_field, y_field=y_field)
    # Money out comes signed negative; a slice or bar then shows its size. A left, net or change
    # field keeps its sign, which is its meaning.
    if (
        isinstance(component, Donut | BarChart)
        and OUTGOING.search(y_field) is not None
        and all(row[y_field] <= 0 for _, row in marks)
    ):
        marks = [(index, {**row, y_field: abs(row[y_field])}) for index, row in marks]
    for index, row in marks:
        # Slices of money in and out, or days on one scale, have no negative size.
        if isinstance(component, Donut | Calendar) and row[y_field] < 0:
            raise BadRequestError(f"{component.data}[{index}].{y_field} is negative")
    if isinstance(component, Donut) and len(marks) > len(SLICES):
        raise BadRequestError(
            f"{component.data} has {len(marks)} parts; a donut shows at most {len(SLICES)}"
        )
    series = [None if series_field is None else str(row[series_field]) for _, row in marks]
    shorts = [short(field=x_field, value=row[x_field]) for _, row in marks]
    # Two rows of one series with the same short label ("Oct" of two years) get the full one.
    is_unique = len(set(zip(series, shorts, strict=True))) == len(marks)
    values = []
    for mark, (index, row) in enumerate(marks):
        full = display(field=x_field, value=row[x_field])
        shown = display(field=y_field, value=row[y_field])
        path = f"{component.data}[{index}]"
        value = {
            "key": str(row[x_field]),
            "label": shorts[mark] if is_unique else full,
            "y": row[y_field],
            "shown": shown,
            "series": series[mark],
            "path": path,
            # What a screen reader says for the mark; the bridge reads the path in brackets.
            "description": f"{full}, {shown} ({path})",
            "booking_ids": row.get("booking_ids", []),
        }
        if isinstance(component, ForecastChart):
            value |= _forecast_fields(
                component=component, row=row, full=full, shown=shown, path=path
            )
        if isinstance(component, Waterfall):
            value |= _step_fields(component=component, row=row, full=full, path=path)
        if isinstance(component, Calendar):
            value |= _day_fields(day=row[x_field])
        values.append(value)
    if isinstance(component, Trend):
        return _sparkline(values=values)
    if isinstance(component, Calendar):
        return _calendar(values=values)
    # A horizontal chart's labels sit beside the plot, so its static plot is narrower.
    labels_beside = isinstance(component, BarChart) and component.horizontal
    size: dict[str, Any] = (
        {"width": "container", "autosize": {"type": "fit-x", "contains": "padding"}}
        if live
        else {"width": STATIC_WIDTH - LABEL_LIMIT if labels_beside else STATIC_WIDTH}
    )
    if isinstance(component, ForecastChart):
        return {**size, **_forecast(values=values, has_range=component.low is not None)}
    if isinstance(component, Waterfall):
        return {**size, **_waterfall(component=component, values=values, data=data)}
    chosen = _chosen(component=component, values=values, has_series=series_field is not None)
    if isinstance(component, Donut):
        colours = [chosen.get(value["key"], SLICES[index]) for index, value in enumerate(values)]
        return _donut(values=values, colours=colours)
    if isinstance(component, BarChart):
        return {**size, **_bar(component=component, values=values, chosen=chosen)}
    scale = _series_scale(series=[value["series"] for value in values], chosen=chosen)
    if isinstance(component, Comparison):
        return {**size, **_comparison(values=values, scale=scale)}
    has_series = series_field is not None
    filled = isinstance(component, AreaChart)
    return {**size, **_line(values=values, has_series=has_series, filled=filled, scale=scale)}


def _one_per_label(
    component: Chart | Trend, found: list[dict[str, Any]], x_field: str, y_field: str
) -> list[tuple[int, dict[str, Any]]]:
    # Rows that repeat a label (in one series) become one mark: their sum, with all bookings.
    series_field = _fields(component=component)[2]
    marks: dict[tuple[Any, str], tuple[int, dict[str, Any]]] = {}
    for index, row in enumerate(found):
        key = (None if series_field is None else str(row[series_field]), str(row[x_field]))
        if key not in marks:
            marks[key] = (index, row)
            continue
        # A step, forecast row or day holds more than its value, so two can't become one.
        if isinstance(component, Waterfall | ForecastChart | Calendar):
            raise BadRequestError(
                f"{component.data}[{index}] repeats {x_field} {key[1]}: a chart shows one "
                "value per label"
            )
        first_index, first = marks[key]
        total = Decimal(str(first[y_field])) + Decimal(str(row[y_field]))
        bookings = first.get("booking_ids", []) + row.get("booking_ids", [])
        marks[key] = (
            first_index,
            {**first, y_field: float(total), "booking_ids": list(dict.fromkeys(bookings))},
        )
    return list(marks.values())


def _chosen(
    component: BarChart | LineChart | AreaChart | Comparison | Donut,
    values: list[dict[str, Any]],
    has_series: bool,
) -> dict[str, str]:
    # The customer's colours by row label or series value; a key the chart lacks is refused.
    if component.colors is None:
        return {}
    if isinstance(component, LineChart | AreaChart) and not has_series:
        raise BadRequestError(
            f"{component.type} without series draws one line: colors needs a series to colour"
        )
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
    if is_periods and len(domain) > len(PERIOD_SERIES):
        raise BadRequestError(
            f"{len(domain)} periods; a chart shows at most {len(PERIOD_SERIES)} side by side"
        )
    base = PERIOD_SERIES if is_periods else SERIES
    colours = [chosen.get(name, base[index % len(base)]) for index, name in enumerate(domain)]
    return {"domain": domain, "range": colours}


def _fields(component: Chart | Trend) -> tuple[str, str, str | None]:
    if isinstance(component, Donut):
        return component.label, component.value, None
    if isinstance(component, Waterfall):
        return component.label, component.amount, None
    if isinstance(component, Calendar):
        return component.date, component.value, None
    if isinstance(component, BarChart | Trend | ForecastChart):
        return component.x, component.y, None
    return component.x, component.y, component.series


def _extra_fields(component: Chart | Trend) -> list[str]:
    # Fields a row needs beside its label, value and series.
    if isinstance(component, ForecastChart):
        return [component.kind]
    if isinstance(component, Waterfall):
        return [component.start, component.end]
    return []


def _check_steps(component: Waterfall, found: list[dict[str, Any]]) -> None:
    # Each step starts where the one before ended, and its amount is the distance it goes.
    for index, row in enumerate(found):
        where = f"{component.data}[{index}]"
        start, end = row[component.start], row[component.end]
        for field in (component.start, component.end):
            if not is_number(value=row[field]):
                raise BadRequestError(f"{where}.{field} is not a number")
        if not agree(row[component.amount], end - start):
            raise BadRequestError(
                f"{where}.{component.amount} is {row[component.amount]}, but the step goes from "
                f"{start} to {end}"
            )
        if index > 0 and not agree(start, found[index - 1][component.end]):
            raise BadRequestError(
                f"{where}.{component.start} is {start}, but the step before ends at "
                f"{found[index - 1][component.end]}: steps must join"
            )


def _check_days(component: Calendar, found: list[dict[str, Any]]) -> None:
    if len(found) == 0:
        raise BadRequestError(f"{component.data} has no days to show")
    days = [_day(component=component, index=index, row=row) for index, row in enumerate(found)]
    first, last = min(days), max(days)
    weeks = (last - timedelta(days=last.weekday())) - (first - timedelta(days=first.weekday()))
    if weeks.days // 7 + 1 > MAX_WEEKS:
        raise BadRequestError(
            f"{component.data} spans {weeks.days // 7 + 1} weeks; a calendar shows at most "
            f"{MAX_WEEKS}"
        )


def _day(component: Calendar, index: int, row: dict[str, Any]) -> date:
    value = row[component.date]
    # A whole day such as "2026-11-27": no time, and one the calendar has ("2026-02-30" isn't).
    try:
        if not is_date(value=value) or len(value) != len("2026-11-27"):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise BadRequestError(
            f"{component.data}[{index}].{component.date} is not a day: {value!r}"
        ) from None


def _check_forecast(component: ForecastChart, found: list[dict[str, Any]]) -> None:
    # A forecast's rows run from actual to forecast; a range needs numbers on the forecast rows.
    seen_forecast = False
    for index, row in enumerate(found):
        where = f"{component.data}[{index}]"
        kind = row[component.kind]
        if kind not in ("actual", "forecast"):
            raise BadRequestError(f"{where}.{component.kind} is {kind!r}: actual or forecast")
        if kind == "actual" and seen_forecast:
            raise BadRequestError(f"{where} is actual after a forecast row: actual rows come first")
        seen_forecast = seen_forecast or kind == "forecast"
        ends = component.range_fields()
        if kind == "actual" or ends is None:
            continue
        low, high = row.get(ends[0]), row.get(ends[1])
        if low is None or high is None or not is_number(value=low) or not is_number(value=high):
            raise BadRequestError(f"{where} needs numbers in {ends[0]} and {ends[1]}")
        if low > high:
            raise BadRequestError(f"{where}.{ends[0]} is above {ends[1]}")
    if not seen_forecast:
        raise BadRequestError(f"{component.data} has no forecast row: use a line_chart")


def _forecast_fields(
    component: ForecastChart, row: dict[str, Any], full: str, shown: str, path: str
) -> dict[str, Any]:
    kind = row[component.kind]
    ends = component.range_fields()
    if kind == "actual":
        return {"kind": kind, "low": None, "high": None, "detail": "actual"}
    if ends is None:
        return {
            "kind": kind,
            "low": None,
            "high": None,
            "detail": "forecast",
            "description": f"{full}, forecast {shown} ({path})",
        }
    low, high = row[ends[0]], row[ends[1]]
    between = (
        f"between {display(field=ends[0], value=low)} and {display(field=ends[1], value=high)}"
    )
    return {
        "kind": kind,
        "low": low,
        "high": high,
        "detail": f"forecast, {between}",
        "description": f"{full}, forecast {shown}, {between} ({path})",
    }


def static_svg(spec: dict[str, Any]) -> str:
    return vl_convert.vegalite_to_svg(
        vl_spec=spec, vl_version=VEGA_LITE_VERSION, config=THEME, format_locale=LOCALE
    )


@cache
def runtime() -> str:
    """Vega, Vega-Lite and Vega-Embed as one script, so a live page needs no network."""
    return vl_convert.javascript_bundle(snippet=GLOBALS, vl_version=VEGA_LITE_VERSION)


@cache
def font_faces() -> str:
    """The fonts as CSS of data URLs, since a widget has no network to load a font from."""
    faces = []
    for name, weight in FONT_WEIGHTS.items():
        data = base64.b64encode((FONTS / f"Inter-{name}.ttf").read_bytes()).decode()
        faces.append(
            f"@font-face{{font-family:Inter;font-weight:{weight};"
            f"src:url(data:font/ttf;base64,{data})}}"
        )
    return "".join(faces)


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
        "stops": [{"offset": 0, "color": SURFACE}, {"offset": 1, "color": "#9cc2be"}],
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


def _forecast(values: list[dict[str, Any]], has_range: bool) -> dict[str, Any]:
    actual = [value for value in values if value["kind"] == "actual"]
    forecast = [value for value in values if value["kind"] == "forecast"]
    # The layers have their own rows, so the order of the months is given, not taken from them.
    x = {
        "field": "label",
        "type": "ordinal",
        "sort": None,
        "scale": {"domain": [value["label"] for value in values]},
        "axis": {"labelOverlap": "greedy"},
    }
    y = {"field": "y", "type": "quantitative", "stack": None, "axis": {"format": ",.0f"}}
    # Lines, range and zero line carry no label of their own; the points name every figure.
    line = {
        "type": "line",
        "interpolate": "monotone",
        "strokeWidth": 2.5,
        "color": ACCENT,
        "aria": False,
    }
    layers: list[dict[str, Any]] = []
    if has_range:
        layers.append(
            {
                "data": {"values": forecast},
                "mark": {
                    "type": "area",
                    "interpolate": "monotone",
                    "color": ACCENT_LIGHT,
                    "aria": False,
                },
                "encoding": {
                    "x": x,
                    "y": {**y, "field": "low"},
                    "y2": {"field": "high"},
                },
            }
        )
    layers += [
        {"data": {"values": actual}, "mark": line, "encoding": {"x": x, "y": y}},
        # The dashed line starts at the last actual point, so the two lines meet.
        {
            "data": {"values": actual[-1:] + forecast},
            "mark": {**line, "strokeDash": [6, 4]},
            "encoding": {"x": x, "y": y},
        },
        # Only the points carry the row's path; forecast points are drawn hollow.
        {
            "mark": {"type": "point", "filled": True, "size": 60, "strokeWidth": 2},
            "encoding": {
                "x": x,
                "y": y,
                "fill": {
                    "condition": {"test": "datum.kind === 'forecast'", "value": SURFACE},
                    "value": ACCENT,
                },
                "stroke": {"value": ACCENT},
                "description": {"field": "description"},
                "tooltip": [*_tooltip(y_title="value"), {"field": "detail", "title": " "}],
            },
        },
    ]
    ends = [value["y"] for value in values] + [
        end for value in forecast for end in (value["low"], value["high"]) if end is not None
    ]
    if min(ends) < 0 < max(ends):
        # A zero line where the series crosses from plus to minus.
        layers.append(
            {
                "data": {"values": [{}]},
                "mark": {"type": "rule", "color": MUTED, "strokeDash": [2, 3], "aria": False},
                "encoding": {"y": {"datum": 0}},
            }
        )
    return {
        "height": LINE_HEIGHT,
        # Room for half of the last month's label, which is centred on the last point.
        "padding": {"left": 0, "right": LAST_LABEL_ROOM, "top": 10, "bottom": 0},
        "data": {"values": values},
        "layer": layers,
    }


def _step_fields(component: Waterfall, row: dict[str, Any], full: str, path: str) -> dict[str, Any]:
    start, end, amount = row[component.start], row[component.end], row[component.amount]
    shown = display(field=component.amount, value=amount)
    since = display(field=component.start, value=start)
    until = display(field=component.end, value=end)
    return {
        "start": start,
        "end": end,
        "top": max(start, end),
        "step": "up" if amount >= 0 else "down",
        # The step's own figure, signed, so up and down don't rest on colour alone.
        "text": ("+" if amount > 0 else "") + number(value=amount, decimals=0),
        "description": f"{full}, {shown}, from {since} to {until} ({path})",
    }


def _day_fields(day: str) -> dict[str, Any]:
    when = date.fromisoformat(day)
    monday = when - timedelta(days=when.weekday())
    return {"week": monday.isoformat(), "weekday": WEEKDAYS[when.weekday()]}


def _waterfall(
    component: Waterfall, values: list[dict[str, Any]], data: dict[str, Any]
) -> dict[str, Any]:
    steps = list(values)
    if component.total is not None:
        total = figure(path=component.total, data=data)
        last_end = values[-1]["end"] if len(values) > 0 else 0
        if not agree(total, last_end):
            raise BadRequestError(
                f"{component.total} is {total}, but the last step ends at {last_end}"
            )
        label = "Left" if component.total_label is None else component.total_label
        # A total named like a step would share its bar.
        if label in {value["label"] for value in values}:
            raise BadRequestError(f"total_label {label!r} is also a step's label")
        shown = display(field=component.total, value=total)
        steps.append(
            {
                "key": label,
                "label": label,
                "y": total,
                "shown": shown,
                "series": None,
                "path": component.total,
                "description": f"{label}, {shown} ({component.total})",
                "booking_ids": [],
                "start": 0,
                "end": total,
                "top": max(0, total),
                "step": "total",
                "text": number(value=total, decimals=0),
            }
        )
    colour = {
        "condition": [
            {"test": "datum.step === 'total'", "value": TEXT},
            {"test": "datum.step === 'down'", "value": STEP_DOWN},
        ],
        "value": ACCENT,
    }
    amount = {"type": "quantitative", "stack": None}
    return {
        "height": BAR_HEIGHT,
        "data": {"values": steps},
        "encoding": {
            "x": {
                "field": "label",
                "type": "ordinal",
                "sort": None,
                "axis": {"labelAngle": -30, "labelLimit": 90},
            },
            "description": {"field": "description"},
        },
        "layer": [
            {
                "mark": {"type": "bar", "cornerRadius": 4, "width": {"band": 0.62}},
                "encoding": {
                    "y": {**amount, "field": "start", "axis": {"format": ",.0f"}},
                    "y2": {"field": "end"},
                    "color": colour,
                    "tooltip": [
                        {"field": "label", "title": " "},
                        {"field": "shown", "title": component.amount},
                    ],
                },
            },
            {
                "mark": {
                    "type": "text",
                    "dy": -8,
                    "fontSize": 12,
                    "fontWeight": 600,
                    "color": TEXT,
                },
                "encoding": {"y": {**amount, "field": "top"}, "text": {"field": "text"}},
            },
        ],
    }


def _calendar(values: list[dict[str, Any]]) -> dict[str, Any]:
    days = [date.fromisoformat(value["key"]) for value in values]
    first, last = min(days), max(days)
    # Every day of the span gets a quiet cell, so the weeks keep their shape.
    span = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
    background = [_day_fields(day=day.isoformat()) for day in span]
    weeks = list(dict.fromkeys(cell["week"] for cell in background))
    # A week is labelled with the month that starts in it, and the first week with its own.
    labelled = {weeks[0]: MONTHS[first.month - 1]}
    for day in span:
        if day.day == 1:
            labelled[(day - timedelta(days=day.weekday())).isoformat()] = MONTHS[day.month - 1]
    x = {
        "field": "week",
        "type": "ordinal",
        "sort": None,
        "scale": {"domain": weeks},
        "axis": {
            "orient": "top",
            "values": list(labelled),
            "labelExpr": f"{json.dumps(list(labelled.values()))}"
            f"[indexof({json.dumps(list(labelled))}, datum.value)]",
            "labelAlign": "left",
        },
    }
    y = {"field": "weekday", "type": "ordinal", "sort": WEEKDAYS, "scale": {"domain": WEEKDAYS}}
    cell = {"type": "rect", "cornerRadius": 2, "stroke": SURFACE, "strokeWidth": 2}
    return {
        "width": {"step": CELL},
        "height": {"step": CELL},
        "data": {"values": values},
        "layer": [
            {
                "data": {"values": background},
                "mark": {**cell, "color": EMPTY_DAY, "aria": False},
                "encoding": {"x": x, "y": y},
            },
            {
                "mark": cell,
                "encoding": {
                    "x": x,
                    "y": y,
                    "color": {
                        "field": "y",
                        "type": "quantitative",
                        "scale": {"type": "sqrt", "range": CALENDAR_RANGE, "zero": True},
                        "legend": {"format": ",.0f", "orient": "bottom", "gradientLength": 120},
                    },
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
            # Bars in each group in the legend's order, newest period first.
            "xOffset": {"field": "series", "type": "nominal", "sort": scale["domain"]},
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
