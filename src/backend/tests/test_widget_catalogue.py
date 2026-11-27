import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.core.errors import BadRequestError
from app.features.widgets.catalogue import render as render_module
from app.features.widgets.catalogue.charts import (
    ACCENT,
    LABEL_LIMIT,
    PALETTE,
    PERIOD_SERIES,
    SERIES,
    chart_spec,
    static_svg,
)
from app.features.widgets.catalogue.prompts import NOT_COMPONENTS, PROMPTS, catalogue_prompt
from app.features.widgets.catalogue.render import Form, fallback, render
from app.features.widgets.catalogue.schemas import (
    COMPONENTS,
    AreaChart,
    BarChart,
    ColourName,
    Comparison,
    ForecastChart,
    LineChart,
    WidgetSpec,
)
from app.features.widgets.catalogue.values import display, resolve

SNAPSHOTS = Path(__file__).with_name("snapshots") / "widget_catalogue"
CHROME = os.environ.get(
    "CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
WIDTHS = (360, 440, 1000)
CHARTS = ("bar_chart", "line_chart", "area_chart", "comparison", "donut", "forecast_chart")
# Sparklines in BODIES: the kpi's and the second stat's.
TRENDS = 2
DATA: dict[str, Any] = {
    "months": [
        {"label": "2026-09", "total_chf": 17273.6, "booking_ids": ["BK-01", "BK-02"]},
        {"label": "2026-10", "total_chf": 10598.77, "booking_ids": ["BK-03"]},
    ],
    "years": [
        {"month": "09", "year": "2025", "total_chf": 18699.41},
        {"month": "10", "year": "2025", "total_chf": 8454.39},
        {"month": "09", "year": "2026", "total_chf": 17273.6},
        {"month": "10", "year": "2026", "total_chf": 10598.77},
    ],
    "payments": [
        {
            "due_date": "2026-11-27",
            "payee": "Wohnbau Sihlfeld AG Liegenschaftsverwaltung",
            "amount_chf": 2800.0,
        },
        {"due_date": "2026-12-01", "payee": "<b>Fitnesspark</b>", "amount_chf": 119.0},
    ],
    "payments_total_chf": 2919.0,
    "months_total_chf": 27872.37,
    "months_change_chf": -6674.83,
    "budget_change_chf": -120.5,
    "goals": [{"name": "Japan 2027", "saved_chf": 9000.0, "goal_chf": 12000.0}],
    "forecast": [
        {"month": "2026-08", "net_chf": 500.0, "kind": "actual", "booking_ids": ["BK-10"]},
        {"month": "2026-09", "net_chf": -200.0, "kind": "actual", "booking_ids": ["BK-11"]},
        {"month": "2026-10", "net_chf": 300.0, "kind": "actual", "booking_ids": ["BK-12"]},
        {
            "month": "2026-11",
            "net_chf": 250.0,
            "kind": "forecast",
            "low_chf": 100.0,
            "high_chf": 300.0,
        },
        {
            "month": "2026-12",
            "net_chf": 200.0,
            "kind": "forecast",
            "low_chf": -50.0,
            "high_chf": 350.0,
        },
    ],
    "rent_cases": [
        {"case": "Rent today", "rent_chf": 2800.0, "left_chf": 912.4},
        {"case": "200 more", "rent_chf": 3000.0, "left_chf": 712.4},
        {"case": "<b>400 more</b>", "rent_chf": 3200.0, "left_chf": 512.4},
    ],
}
BODIES: dict[str, dict[str, Any]] = {
    "kpi": {
        "type": "kpi",
        "label": "Spending",
        "value": "months[1].total_chf",
        "compare": "months[0].total_chf",
        "compare_label": "September",
        "trend": {"data": "months", "x": "label", "y": "total_chf"},
        "change": "months_change_chf",
        "good_when": "down",
    },
    "stat_row": {
        "type": "stat_row",
        "stats": [
            {"label": "September", "value": "months[0].total_chf"},
            {
                "label": "October",
                "value": "months[1].total_chf",
                "trend": {"data": "months", "x": "label", "y": "total_chf"},
                "change": "months_change_chf",
                "good_when": "down",
            },
        ],
    },
    "table": {
        "type": "table",
        "rows": "payments",
        "columns": ["due_date", "payee", "amount_chf"],
        "total": "payments_total_chf",
    },
    "list": {
        "type": "list",
        "rows": "payments",
        "label": "payee",
        "detail": "due_date",
        "value": "amount_chf",
    },
    "bar_chart": {
        "type": "bar_chart",
        "data": "months",
        "x": "label",
        "y": "total_chf",
        "highlight": "2026-10",
    },
    "line_chart": {
        "type": "line_chart",
        "data": "years",
        "x": "month",
        "y": "total_chf",
        "series": "year",
    },
    "timeline": {
        "type": "timeline",
        "rows": "payments",
        "date": "due_date",
        "label": "payee",
        "value": "amount_chf",
    },
    "area_chart": {
        "type": "area_chart",
        "data": "years",
        "x": "month",
        "y": "total_chf",
        "series": "year",
    },
    "comparison": {
        "type": "comparison",
        "data": "years",
        "x": "month",
        "y": "total_chf",
        "series": "year",
    },
    "donut": {
        "type": "donut",
        "data": "months",
        "label": "label",
        "value": "total_chf",
        "total": "months_total_chf",
    },
    "forecast_chart": {
        "type": "forecast_chart",
        "data": "forecast",
        "x": "month",
        "y": "net_chf",
        "kind": "kind",
        "low": "low_chf",
        "high": "high_chf",
    },
    "scenarios": {
        "type": "scenarios",
        "data": "rent_cases",
        "label": "case",
        "figures": [
            {"label": "Rent", "field": "rent_chf"},
            {"label": "Left over", "field": "left_chf"},
        ],
    },
    "progress": {
        "type": "progress",
        "label": "Japan 2027",
        "value": "goals[0].saved_chf",
        "goal": "goals[0].goal_chf",
    },
    "callout": {"type": "callout", "title": "Note", "text": "Rent is due this week."},
    "stack": {
        "type": "stack",
        "children": [{"type": "kpi", "label": "Total", "value": "payments_total_chf"}],
    },
    "grid": {
        "type": "grid",
        "columns": 2,
        "children": [
            {"type": "kpi", "label": "Sep", "value": "months[0].total_chf"},
            {"type": "kpi", "label": "Oct", "value": "months[1].total_chf"},
        ],
    },
}


def spec(body: dict[str, Any]) -> WidgetSpec:
    return WidgetSpec.model_validate({"title": "Spending", "subtitle": "Sample", "body": body})


@pytest.mark.parametrize("name", list(BODIES))
def test_each_component_renders_as_stored(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Without the 900 KB Vega runtime, the live page is our own HTML and chart specs only.
    monkeypatch.setattr(render_module, "runtime", lambda: "")
    page = render(spec=spec(body=BODIES[name]), data=DATA, form="live")
    snapshot = SNAPSHOTS / f"{name}.html"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(page, encoding="utf-8")
    assert page == snapshot.read_text(encoding="utf-8")


def test_figures_are_formatted_swiss_and_text_is_escaped() -> None:
    page = render(spec=spec(body=BODIES["table"]), data=DATA, form="static")
    assert "CHF 2&#39;800.00" in page
    assert "27.11.2026" in page
    assert "&lt;b&gt;Fitnesspark&lt;/b&gt;" in page
    assert "<b>Fitnesspark</b>" not in page


def test_a_closing_script_in_a_title_and_a_quote_in_highlight_render_safely() -> None:
    body = {**BODIES["bar_chart"], "highlight": 'Oct "26'}
    hostile = WidgetSpec.model_validate(
        {"title": "</script><script>alert(1)</script>", "body": body}
    )
    for form in ("live", "static"):
        page = render(spec=hostile, data=DATA, form=form)
        assert "</script><script>alert(1)" not in page
        assert "&lt;/script&gt;&lt;script&gt;alert(1)" in page
    live = render(spec=hostile, data=DATA, form="live")
    assert 'datum.key === \\"Oct \\\\\\"26\\"' in live


@pytest.mark.parametrize(
    ("good_when", "tone", "verdict"),
    [("down", "change good", "good"), ("up", "change bad", "to watch")],
)
def test_a_change_is_coloured_by_whether_it_goes_the_good_way(
    good_when: str, tone: str, verdict: str
) -> None:
    body = {
        "type": "kpi",
        "label": "Groceries",
        "value": "months[1].total_chf",
        "change": "budget_change_chf",
        "good_when": good_when,
    }
    page = render(spec=spec(body=body), data=DATA, form="static")
    change = re.search(r'<span class="change [^>]*>.*?</span></span>', page)
    assert change is not None
    assert f'class="{tone}"' in change.group(0)
    assert "▼</span> CHF 120.50 less" in change.group(0)
    # The verdict is written out too, not shown by colour alone.
    assert f'<span class="verdict">{verdict}</span>' in change.group(0)


def test_no_change_is_neutral_and_a_change_needs_a_number_and_a_way() -> None:
    body = {**BODIES["kpi"], "change": "zero_chf"}
    page = render(spec=spec(body=body), data={**DATA, "zero_chf": 0}, form="static")
    assert 'class="change neutral"' in page
    assert "CHF 0.00 no change" in page
    with pytest.raises(ValidationError, match="good_when"):
        spec(body={"type": "kpi", "label": "X", "value": "months[1].total_chf", "change": "x"})
    with pytest.raises(BadRequestError, match="not a number"):
        render(spec=spec(body={**BODIES["kpi"], "change": "goals"}), data=DATA, form="static")


def test_a_trend_draws_a_sparkline_in_both_forms() -> None:
    static = render(spec=spec(body=BODIES["kpi"]), data=DATA, form="static")
    trend = re.search(r'<div class="trend" .*?</div></div>', static, re.DOTALL)
    assert trend is not None
    assert "<svg" in trend.group(0)
    assert 'data-path="months"' in trend.group(0)
    assert "BK-03" in trend.group(0)
    live = render(spec=spec(body=BODIES["kpi"]), data=DATA, form="live")
    assert '"id": "chart-1"' in live
    assert 'class="chart-area trend-area" id="chart-1"></div>' in live


def test_the_total_sits_under_its_amount_column() -> None:
    swapped = {**BODIES["table"], "columns": ["amount_chf", "payee"]}
    page = render(spec=spec(body=swapped), data=DATA, form="static")
    total = re.search(r"<tfoot[^>]*>.*?</tfoot>", page, re.DOTALL)
    assert total is not None
    cells = re.findall(r"<td[^>]*>([^<]*)</td>", total.group(0))
    assert cells == ["CHF 2&#39;919.00", "Total"]
    alone = render(
        spec=spec(body={**BODIES["table"], "columns": ["amount_chf"]}), data=DATA, form="static"
    )
    assert "Total CHF 2&#39;919.00" in alone


def test_a_total_without_a_column_for_it_is_refused() -> None:
    with pytest.raises(ValidationError, match="a total needs a column"):
        spec(body={**BODIES["table"], "columns": ["due_date", "payee"]})


def test_a_cut_table_says_how_many_rows_it_shows() -> None:
    rows = [{"payee": f"Payee {index}", "amount_chf": 1.0} for index in range(60)]
    body = {"type": "table", "rows": "rows", "columns": ["payee", "amount_chf"]}
    page = render(spec=spec(body=body), data={"rows": rows}, form="static")
    assert "First 50 of 60 rows" in page
    assert page.count('data-component="table-row"') == 50


def test_a_figure_carries_the_booking_ids_of_its_row() -> None:
    page = render(spec=spec(body=BODIES["kpi"]), data=DATA, form="static")
    assert (
        'data-path="months[1].total_chf" data-value="10598.77" data-booking-ids="[&#34;BK-03&#34;]"'
        in page
    )


def test_a_chart_refuses_two_rows_with_one_label() -> None:
    # Vega-Lite would draw their sum, 150, which DATA doesn't hold.
    payees = [{"label": "Migros", "total_chf": 100.0}, {"label": "Migros", "total_chf": 50.0}]
    body = {"type": "bar_chart", "data": "payees", "x": "label", "y": "total_chf"}
    with pytest.raises(BadRequestError, match=r"payees\[1\] repeats label Migros"):
        render(spec=spec(body=body), data={"payees": payees}, form="static")


def test_a_figure_must_be_a_number() -> None:
    with pytest.raises(BadRequestError, match=r"months\[0\] is a dict, not a number"):
        render(
            spec=spec(body={"type": "kpi", "label": "x", "value": "months[0]"}),
            data=DATA,
            form="static",
        )
    with pytest.raises(BadRequestError, match="months is a list, not a number"):
        render(
            spec=spec(body={"type": "kpi", "label": "x", "value": "months"}),
            data=DATA,
            form="static",
        )
    body = {"type": "table", "rows": "months", "columns": ["label", "booking_ids"]}
    with pytest.raises(BadRequestError, match=r"months\[0\].booking_ids is a list"):
        render(spec=spec(body=body), data=DATA, form="static")


def test_a_total_that_is_not_the_sum_of_its_column_is_refused() -> None:
    wrong = {**DATA, "payments_total_chf": 3000.0}
    with pytest.raises(
        BadRequestError, match="payments_total_chf is 3000.0, but the amount_chf column"
    ):
        render(spec=spec(body=BODIES["table"]), data=wrong, form="static")


def test_a_donut_refuses_a_negative_part_and_a_total_that_is_not_its_sum() -> None:
    negative = {"months": [{"label": "2026-10", "total_chf": -5.0}], "months_total_chf": -5.0}
    with pytest.raises(BadRequestError, match=r"months\[0\].total_chf is negative"):
        render(spec=spec(body=BODIES["donut"]), data=negative, form="static")
    with pytest.raises(BadRequestError, match="months_total_chf is 1.0, but the total_chf column"):
        render(
            spec=spec(body=BODIES["donut"]), data={**DATA, "months_total_chf": 1.0}, form="static"
        )


def test_a_donut_lists_every_part_with_its_bookings() -> None:
    page = render(spec=spec(body=BODIES["donut"]), data=DATA, form="static")
    assert page.count('data-component="donut-slice"') == 2
    assert (
        'data-path="months[1]" data-value="10598.77" data-booking-ids="[&#34;BK-03&#34;]"' in page
    )
    assert "CHF 27&#39;872.37" in page


def test_progress_draws_a_capped_bar_and_writes_no_share() -> None:
    page = render(spec=spec(body=BODIES["progress"]), data=DATA, form="static")
    assert 'style="width: 75.0%"' in page
    assert "CHF 9&#39;000.00" in page
    assert "Goal CHF 12&#39;000.00" in page
    body = re.search(r"<main.*</main>", page, re.DOTALL)
    assert body is not None
    assert "75" not in re.sub(r'style="[^"]*"', "", body.group(0))
    above = {**DATA, "goals": [{"name": "x", "saved_chf": 37566.29, "goal_chf": 12000.0}]}
    assert 'style="width: 100.0%"' in render(
        spec=spec(body=BODIES["progress"]), data=above, form="static"
    )
    zero = {**DATA, "goals": [{"name": "x", "saved_chf": 1.0, "goal_chf": 0}]}
    with pytest.raises(BadRequestError, match="a goal must be above zero"):
        render(spec=spec(body=BODIES["progress"]), data=zero, form="static")


def test_a_donut_shows_at_most_one_part_per_colour() -> None:
    months = [{"label": f"2026-{index:02d}", "total_chf": 1.0} for index in range(1, 11)]
    body = {"type": "donut", "data": "months", "label": "label", "value": "total_chf"}
    with pytest.raises(BadRequestError, match="months has 10 parts; a donut shows at most 9"):
        render(spec=spec(body=body), data={"months": months}, form="static")


def test_a_timeline_needs_dates_in_order() -> None:
    swapped = {**DATA, "payments": DATA["payments"][::-1]}
    with pytest.raises(BadRequestError, match=r"payments\[1\].due_date comes before the row above"):
        render(spec=spec(body=BODIES["timeline"]), data=swapped, form="static")
    undated = {**DATA, "payments": [{**DATA["payments"][0], "due_date": "soon"}]}
    with pytest.raises(BadRequestError, match=r"payments\[0\].due_date is not a date"):
        render(spec=spec(body=BODIES["timeline"]), data=undated, form="static")


def test_a_comparison_needs_its_period_field() -> None:
    with pytest.raises(ValidationError):
        spec(body={key: value for key, value in BODIES["comparison"].items() if key != "series"})


def _contrast_on_white(colour: str) -> float:
    channels = [int(colour[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return 1.05 / (luminance + 0.05)


def test_every_palette_and_period_colour_is_readable_on_white() -> None:
    assert set(PALETTE) == set(get_args(ColourName))
    for name, colour in [*PALETTE.items(), *enumerate(PERIOD_SERIES)]:
        assert _contrast_on_white(colour=colour) >= 3, name
    assert ACCENT not in PERIOD_SERIES[1:]


def _fills(svg: str, path: str) -> list[str]:
    # The fills of the static marks whose screen-reader label ends with the row's path.
    tags = re.findall(r"<[^>]*\(" + re.escape(path) + r"\)\"[^>]*>", svg)
    return [fill for tag in tags for fill in re.findall(r'fill="(#[0-9a-f]{6})"', tag)]


def _scale(body: dict[str, Any], live: bool) -> dict[str, Any]:
    chart = spec(body=body).body
    assert isinstance(chart, LineChart | AreaChart | Comparison)
    return chart_spec(component=chart, data=DATA, live=live)["encoding"]["color"]["scale"]


@pytest.mark.parametrize("name", ["line_chart", "area_chart", "comparison"])
def test_the_newest_period_gets_the_accent_colour_in_both_forms(name: str) -> None:
    for live in (True, False):
        assert _scale(body=BODIES[name], live=live) == {
            "domain": ["2026", "2025"],
            "range": [ACCENT, PALETTE["grey_light"]],
        }
    chart = spec(body=BODIES[name]).body
    assert isinstance(chart, LineChart | AreaChart | Comparison)
    svg = static_svg(spec=chart_spec(component=chart, data=DATA, live=False))
    # years[2] is a 2026 row, years[0] a 2025 one.
    assert ACCENT in _fills(svg=svg, path="years[2]")
    assert PALETTE["grey_light"] in _fills(svg=svg, path="years[0]")


def test_a_comparison_draws_its_bars_in_the_legends_order() -> None:
    chart = spec(body=BODIES["comparison"]).body
    assert isinstance(chart, Comparison)
    encoding = chart_spec(component=chart, data=DATA, live=True)["encoding"]
    assert encoding["xOffset"]["sort"] == encoding["color"]["scale"]["domain"] == ["2026", "2025"]


def test_more_periods_than_colours_are_refused() -> None:
    years = [
        {"month": "09", "year": str(year), "total_chf": 1.0}
        for year in range(2026 - len(PERIOD_SERIES), 2027)
    ]
    with pytest.raises(BadRequestError, match=f"at most {len(PERIOD_SERIES)}"):
        render(spec=spec(body=BODIES["line_chart"]), data={"years": years}, form="static")


def test_series_that_are_not_periods_keep_their_order() -> None:
    accounts = {
        "years": [
            {"month": "09", "year": "Savings", "total_chf": 1.0},
            {"month": "09", "year": "Private", "total_chf": 2.0},
        ]
    }
    chart = spec(body=BODIES["line_chart"]).body
    assert isinstance(chart, LineChart)
    scale = chart_spec(component=chart, data=accounts, live=False)["encoding"]["color"]["scale"]
    assert scale == {"domain": ["Private", "Savings"], "range": SERIES[:2]}


def _bar_colour(body: dict[str, Any]) -> tuple[Any, list[str]]:
    chart = spec(body=body).body
    assert isinstance(chart, BarChart)
    bar_spec = chart_spec(component=chart, data=DATA, live=True)
    condition = bar_spec["layer"][0]["encoding"]["color"]["condition"]
    static = static_svg(spec=chart_spec(component=chart, data=DATA, live=False))
    # months[1] is the 2026-10 row.
    return condition, _fills(svg=static, path="months[1]")


def test_a_chosen_colour_draws_its_bar_in_both_forms() -> None:
    condition, fills = _bar_colour(body={**BODIES["bar_chart"], "colors": {"2026-10": "red"}})
    assert {"test": 'datum.key === "2026-10"', "value": PALETTE["red"]} in condition
    assert PALETTE["red"] in fills


def test_highlight_color_draws_the_highlight_in_both_forms() -> None:
    condition, fills = _bar_colour(body={**BODIES["bar_chart"], "highlight_color": "blue"})
    assert condition == {"test": 'datum.key === "2026-10"', "value": PALETTE["blue"]}
    assert PALETTE["blue"] in fills


def test_colours_that_would_do_nothing_are_refused() -> None:
    with pytest.raises(ValidationError, match="highlight_color needs highlight"):
        body = {key: value for key, value in BODIES["bar_chart"].items() if key != "highlight"}
        spec(body={**body, "highlight_color": "blue"})
    single = {"type": "line_chart", "data": "months", "x": "label", "y": "total_chf"}
    with pytest.raises(BadRequestError, match="without series draws one line"):
        render(spec=spec(body={**single, "colors": {"2026-10": "red"}}), data=DATA, form="static")


def test_a_chosen_colour_changes_a_series_and_a_donut_part_with_its_legend() -> None:
    line = {**BODIES["line_chart"], "colors": {"2025": "blue"}}
    chart = spec(body=line).body
    assert isinstance(chart, LineChart)
    scale = chart_spec(component=chart, data=DATA, live=False)["encoding"]["color"]["scale"]
    assert scale["range"] == [ACCENT, PALETTE["blue"]]
    donut = {**BODIES["donut"], "colors": {"2026-09": "amber"}}
    page = render(spec=spec(body=donut), data=DATA, form="static")
    # The legend's swatch matches the slice the customer coloured.
    assert f'style="background: {PALETTE["amber"]}"' in page


def test_an_unknown_colour_or_label_is_refused_with_what_is_allowed() -> None:
    with pytest.raises(ValidationError, match="red_light"):
        spec(body={**BODIES["bar_chart"], "colors": {"2026-10": "purple"}})
    with pytest.raises(BadRequestError, match="colors names '2026-12'.*2026-09, 2026-10"):
        body = {**BODIES["bar_chart"], "colors": {"2026-12": "red"}}
        render(spec=spec(body=body), data=DATA, form="static")


def test_the_prompt_names_the_palette_and_how_to_colour_a_bar() -> None:
    prompt = catalogue_prompt()
    assert "colors (map from a label or series value" in prompt
    assert "amber_light" in prompt
    assert '"colors": {"2026-10": "red"}' in prompt


def test_callout_and_timeline_text_is_escaped() -> None:
    body = {"type": "callout", "title": '"Note"', "text": "</script><script>alert(1)</script>"}
    page = render(spec=spec(body=body), data=DATA, form="live")
    assert "</script><script>alert(1)" not in page
    assert "&lt;/script&gt;&lt;script&gt;alert(1)" in page
    timeline = render(spec=spec(body=BODIES["timeline"]), data=DATA, form="static")
    assert "&lt;b&gt;Fitnesspark&lt;/b&gt;" in timeline
    assert "01.12.2026" in timeline


def test_counts_and_years_keep_plain_digits_and_only_whole_dates_are_dates() -> None:
    assert display(field="year", value=2026) == "2026"
    assert display(field="bookings", value=1234) == "1234"
    assert display(field="amount", value=1234) == "1'234"
    assert display(field="total_chf", value=1234) == "CHF 1'234.00"
    assert display(field="due_date", value="2026-10-01") == "01.10.2026"
    assert display(field="text", value="2026-10-01 Migros Zurich") == "2026-10-01 Migros Zurich"


def test_the_prompt_names_the_size_limits() -> None:
    prompt = catalogue_prompt()
    assert (
        "stats (list of {label, value: path into DATA, and optional trend, change and good_when "
        "as in kpi}, 2 to 4 items)"
    ) in prompt
    assert "trend ({data: path into DATA, x and y: field names of its rows}, optional)" in prompt
    assert "good_when (one of up, down, optional)" in prompt
    assert "columns (list of field names of the rows, 1 to 5 items)" in prompt
    assert "label (text, at most 80 characters)" in prompt


def test_a_static_chart_lists_its_rows_for_clicks() -> None:
    page = render(spec=spec(body=BODIES["bar_chart"]), data=DATA, form="static")
    rows = re.search(r'data-rows="([^"]*)"', page)
    assert rows is not None
    assert "months[1]" in rows.group(1)
    assert "BK-03" in rows.group(1)


def test_two_rows_with_the_same_short_label_keep_apart() -> None:
    months = [
        {"label": "2025-10", "total_chf": 8454.39},
        {"label": "2026-10", "total_chf": 10598.77},
    ]
    body = {"type": "bar_chart", "data": "months", "x": "label", "y": "total_chf"}
    page = render(spec=spec(body=body), data={"months": months}, form="static")
    assert "Oct 2025" in page
    assert "Oct 2026" in page


def test_static_chart_is_svg_with_swiss_labels_and_no_runtime() -> None:
    page = render(spec=spec(body=BODIES["bar_chart"]), data=DATA, form="static")
    assert "<svg" in page
    assert "17'274" in page
    assert "window.trustroomCharts({" not in page
    assert len(page) < 500_000


def test_missing_path_names_what_exists() -> None:
    with pytest.raises(BadRequestError, match="no field month; fields: months, years"):
        resolve(path="month[0].total_chf", data=DATA)
    with pytest.raises(BadRequestError, match="months has 2 items, no index 5"):
        resolve(path="months[5].total_chf", data=DATA)
    with pytest.raises(BadRequestError, match=r"payments\[0\] has no field amount"):
        body = {**BODIES["table"], "columns": ["amount", "amount_chf"]}
        render(spec=spec(body=body), data=DATA, form="static")
    # Every row is checked, not only the first.
    ragged = {"payments": [*DATA["payments"], {"payee": "Coop"}], "payments_total_chf": 1.0}
    with pytest.raises(BadRequestError, match=r"payments\[2\] has no field due_date"):
        render(spec=spec(body=BODIES["table"]), data=ragged, form="static")


@pytest.mark.parametrize("value", [10598.77, "10598.77", "CHF 10'598.77"])
def test_a_figure_where_a_path_belongs_is_refused(value: Any) -> None:
    with pytest.raises(ValidationError):
        spec(body={"type": "kpi", "label": "October", "value": value})


def test_fallback_draws_a_table_or_a_figure_from_data_alone() -> None:
    table = fallback(data=DATA)
    assert table.body.model_dump()["rows"] == "months"
    assert table.body.model_dump()["columns"] == ["label", "total_chf"]
    kpi = fallback(data={"note": "none", "total_chf": 12.5})
    assert kpi.body.model_dump()["value"] == "total_chf"
    assert "CHF 12.50" in render(spec=kpi, data={"total_chf": 12.5}, form="static")


def test_fallback_skips_what_it_cannot_show() -> None:
    data = {
        "bad key": [{"payee": "Migros"}],
        "nested": [{"ids": ["BK-1"], "parts": {"a": 1}}],
        "ragged": [{"payee": "Migros", "extra": 1}, {"payee": "Coop"}],
    }
    table = fallback(data=data)
    assert table.body.model_dump()["rows"] == "ragged"
    assert table.body.model_dump()["columns"] == ["payee"]
    with pytest.raises(BadRequestError, match="no rows and no figure"):
        fallback(data={"note": "none", "flag": True})


def test_every_component_is_in_the_prompt_with_an_example_that_validates() -> None:
    prompt = catalogue_prompt()
    names = [key for key in PROMPTS if key not in NOT_COMPONENTS]
    assert len(names) == len(COMPONENTS)
    for name in names:
        assert spec(body=PROMPTS[name]["example"]).body.type == name
        assert f"\n{name}: " in prompt


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
@pytest.mark.parametrize("form", ["static", "live"])
def test_no_widget_scrolls_sideways(form: Form) -> None:
    body = {
        "type": "stack",
        "children": [
            BODIES[name]
            for name in ("kpi", "stat_row", "table", "list", "timeline", "progress", "callout")
        ]
        + [
            {
                "type": "stack",
                "children": [BODIES[name] for name in (*CHARTS, "grid", "scenarios")],
            }
        ],
    }
    page = render(spec=spec(body=body), data=DATA, form=form)
    measure = (
        "var r=document.documentElement;return (r.scrollWidth > r.clientWidth + 1)"
        "+':'+document.querySelectorAll('.chart-area svg').length;"
    )
    # Every chart and sparkline drawn, by the browser (live) or as SVG from the server (static).
    assert _at_widths(page=page, measure=measure) == sorted(
        f"{w}:false:{len(CHARTS) + TRENDS}" for w in WIDTHS
    )


PHONE_DATA: dict[str, Any] = {
    "payees": [
        {"label": "Wohnbau Sihlfeld AG Liegenschaftsverwaltung", "total_chf": 8400.0},
        {"label": "Steueramt der Stadt Zürich", "total_chf": 6500.0},
        {"label": "Mythen Krankenversicherung AG", "total_chf": 1402.2},
        {"label": "Other", "total_chf": 13051.19},
    ],
    "payments": [
        {
            "due_date": "2026-11-27",
            "payee": "Wohnbau Sihlfeld AG Liegenschaftsverwaltung",
            "description": "Miete Dezember 2026",
            "type": "standing_order",
            "amount_chf": 2800.0,
        },
        {
            "due_date": "2026-12-01",
            "payee": "Fitnesspark Zürich Stadelhofen",
            "description": "Mitgliedschaft Dezember 2026",
            "type": "direct_debit",
            "amount_chf": 119.0,
        },
    ],
    "payments_total_chf": 2919.0,
    "categories": [
        {"category": "Groceries", "this_month_chf": 612.4, "last_month_chf": 540.0},
        {"category": "Restaurants", "this_month_chf": 210.0, "last_month_chf": 388.5},
    ],
    "last_month_chf": 928.5,
}


def test_long_bar_labels_are_cut_and_named_in_full_in_the_tooltip() -> None:
    bars = BarChart.model_validate(
        {"type": "bar_chart", "data": "payees", "x": "label", "y": "total_chf", "horizontal": True}
    )
    chart = chart_spec(component=bars, data=PHONE_DATA, live=True)
    assert chart["encoding"]["y"]["axis"]["labelLimit"] == LABEL_LIMIT
    tooltip = chart["layer"][0]["encoding"]["tooltip"]
    assert {"field": "label", "title": " "} in tooltip
    assert chart["data"]["values"][0]["label"] == "Wohnbau Sihlfeld AG Liegenschaftsverwaltung"


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_a_total_sits_under_its_own_amount_column_at_every_width() -> None:
    body = {
        "type": "table",
        "rows": "categories",
        "columns": ["category", "this_month_chf", "last_month_chf"],
        "total": "last_month_chf",
    }
    page = render(spec=spec(body=body), data=PHONE_DATA, form="static")
    # The total and the first row's cell of its column: same place in their rows, same label.
    measure = (
        "var foot=document.querySelector('tfoot tr'),cells=Array.from(foot.children);"
        "var i=cells.findIndex(function(c){"
        "return c.textContent.trim()!==''&&c.classList.contains('num');});"
        "var row=document.querySelector('tbody tr'),cell=row.children[i];"
        "var a=cells[i].getBoundingClientRect(),b=cell.getBoundingClientRect();"
        "var fa=foot.getBoundingClientRect(),rb=row.getBoundingClientRect();"
        "var same=Math.abs(a.right-b.right)<=1&&Math.abs((a.top-fa.top)-(b.top-rb.top))<=1;"
        "var label=getComputedStyle(cells[i],'::before').content;"
        "return same+':'+(label===getComputedStyle(cell,'::before').content);"
    )
    assert _at_widths(page=page, measure=measure) == sorted(f"{w}:true:true" for w in WIDTHS)


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
@pytest.mark.parametrize("form", ["static", "live"])
def test_long_labels_and_wide_tables_stay_inside_the_widget(form: Form) -> None:
    body = {
        "type": "stack",
        "children": [
            {
                "type": "bar_chart",
                "data": "payees",
                "x": "label",
                "y": "total_chf",
                "horizontal": True,
            },
            {
                "type": "table",
                "rows": "payments",
                "columns": ["due_date", "payee", "description", "type", "amount_chf"],
                "total": "payments_total_chf",
            },
        ],
    }
    page = render(spec=spec(body=body), data=PHONE_DATA, form=form)
    # How far any bar or label leaves its SVG, how far the table scrolls, whether the total shows.
    measure = (
        "var s=document.querySelector('.chart-area svg'),b=s.getBoundingClientRect(),worst=0;"
        "s.querySelectorAll('text,path,rect').forEach(function(e){var r=e.getBoundingClientRect();"
        "if(r.width>0)worst=Math.max(worst,r.right-b.right,b.left-r.left);});"
        "var t=document.querySelector('.table-scroll');"
        "var total=document.querySelector('tfoot td.num');"
        "var shown=total.getBoundingClientRect().right<=t.getBoundingClientRect().right+1;"
        "return Math.round(worst)+':'+(t.scrollWidth-t.clientWidth)+':'+shown;"
    )
    assert _at_widths(page=page, measure=measure) == sorted(f"{w}:0:0:true" for w in WIDTHS)


def _at_widths(page: str, measure: str) -> list[str]:
    """Load the page in iframes of every width; `measure` (a function body) runs in each."""
    probe = (
        "<script>setTimeout(function(){parent.postMessage({probe: true, width: innerWidth, "
        f"result: (function(){{{measure}}})()}}, '*')}}, 2000)</script></body>"
    )
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        # The Vega bundle holds "</body>" in a string, so the probe goes before the last one.
        head, _, tail = page.rpartition("</body>")
        (root / "widget.html").write_text(head + probe + tail, encoding="utf-8")
        frames = "".join(
            f'<iframe src="widget.html" style="width:{w}px;height:900px;border:0"></iframe>'
            for w in WIDTHS
        )
        host = (
            "<!doctype html><body>"
            + frames
            + "<script>var seen=[];addEventListener('message',function(e){if(!e.data.probe)return;"
            "seen.push(e.data.width+':'+e.data.result);document.body.setAttribute('data-seen',seen.sort().join(','))})</script></body>"
        )
        (root / "host.html").write_text(host, encoding="utf-8")
        result = subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                f"--user-data-dir={root / 'profile'}",
                "--window-size=1900,1000",
                "--virtual-time-budget=8000",
                "--dump-dom",
                (root / "host.html").as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    seen = re.search(r'data-seen="([^"]*)"', result.stdout)
    assert seen is not None, result.stderr[-500:]
    return sorted(seen.group(1).split(","))


def _live_mark(kind: str) -> str:
    """A script expression for the last mark of a Vega mark type that belongs to a row."""
    return (
        "Array.from(document.querySelectorAll('.chart-area svg *')).filter(function(e){"
        "var d=e.__data__;return d&&d.mark&&d.datum&&d.datum.path"
        f"&&d.mark.marktype==='{kind}';}}).pop()"
    )


def _clicks(body: dict[str, Any], targets: list[str], form: Form = "live") -> str:
    """Click each target (a script expression) in turn; the rows the page reported."""
    page = render(spec=spec(body=body), data=DATA, form=form)
    click = (
        "<script>setTimeout(function(){"
        + "".join(
            f"{target}.dispatchEvent(new MouseEvent('click',{{bubbles:true}}));"
            for target in targets
        )
        + "},2000)</script></body>"
    )
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        head, _, tail = page.rpartition("</body>")
        (root / "widget.html").write_text(head + click + tail, encoding="utf-8")
        host = (
            '<!doctype html><body><iframe src="widget.html" style="width:440px;height:600px">'
            "</iframe><script>var picks=[];addEventListener('message',function(e){"
            "if(e.data.type!=='widget-select')return;picks.push(e.data.path+' '"
            "+e.data.booking_ids.join('+'));document.body.setAttribute('data-picked',"
            "picks.join('|'))})</script></body>"
        )
        (root / "host.html").write_text(host, encoding="utf-8")
        result = subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                f"--user-data-dir={root / 'profile'}",
                "--window-size=900,700",
                "--virtual-time-budget=8000",
                "--dump-dom",
                (root / "host.html").as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    picked = re.search(r'data-picked="([^"]*)"', result.stdout)
    return "" if picked is None else picked.group(1)


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_live_bar_reports_its_row() -> None:
    assert _clicks(body=BODIES["bar_chart"], targets=[_live_mark(kind="rect")]) == "months[1] BK-03"


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_live_line_reports_only_its_points() -> None:
    # The line is one shape for all rows, so a click on it reports nothing.
    targets = [_live_mark(kind="line"), _live_mark(kind="symbol")]
    assert _clicks(body=BODIES["line_chart"], targets=targets) == "years[3] "


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_live_slice_or_comparison_bar_reports_its_row() -> None:
    assert _clicks(body=BODIES["donut"], targets=[_live_mark(kind="arc")]) == "months[1] BK-03"
    assert _clicks(body=BODIES["comparison"], targets=[_live_mark(kind="rect")]) == "years[3] "


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_live_area_reports_only_its_points() -> None:
    targets = [_live_mark(kind="area"), _live_mark(kind="symbol")]
    assert _clicks(body=BODIES["area_chart"], targets=targets) == "years[3] "


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_sparkline_point_reports_its_row_in_both_forms() -> None:
    kpi = BODIES["kpi"]
    live = _clicks(body=kpi, targets=[_live_mark(kind="symbol")])
    assert live == "months[1] BK-03"
    first = "document.querySelector('.trend [aria-label$=\"(months[0])\"]')"
    assert _clicks(body=kpi, targets=[first], form="static") == "months[0] BK-01+BK-02"


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_static_bar_reports_its_row_and_bookings() -> None:
    bar = "document.querySelector('.chart-area [aria-label$=\"(months[1])\"]')"
    assert _clicks(body=BODIES["bar_chart"], targets=[bar], form="static") == "months[1] BK-03"


def _forecast_spec(**changes: Any) -> dict[str, Any]:
    body = ForecastChart.model_validate({**BODIES["forecast_chart"], **changes})
    return chart_spec(component=body, data=DATA, live=True)


def test_a_forecast_draws_actual_solid_forecast_dashed_and_its_range() -> None:
    layers = _forecast_spec()["layer"]
    band, solid, dashed, points, zero = layers
    # Every layer places the months in DATA's order, whatever rows it draws itself.
    months = ["Aug", "Sep", "Oct", "Nov", "Dec"]
    for layer in (band, solid, dashed, points):
        assert layer["encoding"]["x"]["scale"]["domain"] == months
    assert band["mark"]["type"] == "area"
    assert band["encoding"]["y"]["field"] == "low" and band["encoding"]["y2"]["field"] == "high"
    assert [value["path"] for value in band["data"]["values"]] == ["forecast[3]", "forecast[4]"]
    assert [value["path"] for value in solid["data"]["values"]] == [
        "forecast[0]",
        "forecast[1]",
        "forecast[2]",
    ]
    assert "strokeDash" not in solid["mark"]
    # The dashed line starts at the last actual point, so the two lines meet.
    assert dashed["mark"]["strokeDash"] == [6, 4]
    assert [value["path"] for value in dashed["data"]["values"]] == [
        "forecast[2]",
        "forecast[3]",
        "forecast[4]",
    ]
    assert "data" not in points and points["encoding"]["description"] == {"field": "description"}
    assert zero["mark"]["type"] == "rule" and zero["encoding"]["y"] == {"datum": 0}


def test_a_forecast_draws_no_zero_line_when_it_stays_above_zero() -> None:
    above = [{**row, "net_chf": 400.0} for row in DATA["forecast"]]
    above[4] = {**above[4], "low_chf": 100.0}
    body = ForecastChart.model_validate(BODIES["forecast_chart"])
    layers = chart_spec(component=body, data={**DATA, "forecast": above}, live=True)["layer"]
    assert [layer["mark"]["type"] for layer in layers] == ["area", "line", "line", "point"]


def test_a_forecast_without_a_range_draws_no_band() -> None:
    layers = _forecast_spec(low=None, high=None)["layer"]
    assert [layer["mark"]["type"] for layer in layers][:3] == ["line", "line", "point"]


def test_a_forecast_reads_its_figures_and_says_which_points_are_forecast() -> None:
    values = _forecast_spec()["data"]["values"]
    assert values[3]["description"] == "Nov 2026, forecast CHF 250.00 (forecast[3])"
    assert values[3]["range"] == "CHF 100.00 to CHF 300.00"
    assert values[0]["description"] == "Aug 2026, CHF 500.00 (forecast[0])"
    assert values[0]["booking_ids"] == ["BK-10"]


@pytest.mark.parametrize(
    ("rows", "error"),
    [
        ([{**DATA["forecast"][0], "kind": "plan"}], "actual or forecast"),
        ([DATA["forecast"][3], DATA["forecast"][0]], "actual after a forecast row"),
        (DATA["forecast"][:3], "no forecast row"),
        ([{**DATA["forecast"][3], "low_chf": 400.0}], "low_chf is above high_chf"),
        ([{**DATA["forecast"][3], "high_chf": None}], "needs numbers in low_chf and high_chf"),
    ],
)
def test_a_forecast_refuses_rows_it_cannot_draw_truthfully(
    rows: list[dict[str, Any]], error: str
) -> None:
    body = ForecastChart.model_validate(BODIES["forecast_chart"])
    with pytest.raises(BadRequestError, match=error):
        chart_spec(component=body, data={"forecast": rows}, live=True)


def test_a_forecast_range_needs_both_ends() -> None:
    with pytest.raises(ValidationError, match="both low and high"):
        ForecastChart.model_validate({**BODIES["forecast_chart"], "high": None})


def test_a_static_forecast_is_svg_with_a_dashed_line_and_labelled_points() -> None:
    page = render(spec=spec(body=BODIES["forecast_chart"]), data=DATA, form="static")
    assert "stroke-dasharray" in page
    assert 'aria-label="Nov 2026, forecast CHF 250.00 (forecast[3])"' in page
    assert '<span><i class="key band" aria-hidden="true"></i>Range</span>' in page


def test_live_scenarios_draw_every_case_and_show_the_first() -> None:
    page = render(spec=spec(body=BODIES["scenarios"]), data=DATA, form="live")
    assert re.findall(r'<input type="radio" name="cases-rent_cases" value="(\d)"', page) == [
        "0",
        "1",
        "2",
    ]
    assert 'value="0" checked>' in page
    panels = re.findall(r'<div class="stats case" data-case="(\d)"[^>]*?( hidden)?>', page)
    assert panels == [("0", ""), ("1", " hidden"), ("2", " hidden")]
    # Each case's figures come from its own row of DATA.
    assert 'data-path="rent_cases[1].left_chf" data-value="712.4"' in page
    assert "CHF 3&#39;200.00" in page
    assert "&lt;b&gt;400 more&lt;/b&gt;" in page and "<b>400 more</b>" not in page


def test_static_scenarios_show_the_first_case_and_a_table_of_all() -> None:
    page = render(spec=spec(body=BODIES["scenarios"]), data=DATA, form="static")
    assert 'type="radio"' not in page
    assert '<p class="case-shown">Rent today</p>' in page
    cases = re.findall(r'data-component="scenario-case" data-path="([^"]*)"', page)
    assert cases == ["rent_cases[0]", "rent_cases[1]", "rent_cases[2]"]
    assert page.count("CHF 712.40") == 1 and page.count("CHF 912.40") == 2


@pytest.mark.parametrize("count", [1, 7])
def test_scenarios_need_two_to_six_cases(count: int) -> None:
    cases = [{"case": f"Case {i}", "rent_chf": 1.0, "left_chf": 1.0} for i in range(count)]
    with pytest.raises(BadRequestError, match=f"has {count} cases"):
        render(spec=spec(body=BODIES["scenarios"]), data={"rent_cases": cases}, form="live")


def test_a_scenario_figure_must_be_a_number() -> None:
    cases = [{**case, "left_chf": "a lot"} for case in DATA["rent_cases"]]
    with pytest.raises(BadRequestError, match="not a number"):
        render(spec=spec(body=BODIES["scenarios"]), data={"rent_cases": cases}, form="static")


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_clicking_a_live_forecast_reports_only_its_points() -> None:
    targets = [_live_mark(kind="line"), _live_mark(kind="area"), _live_mark(kind="symbol")]
    assert _clicks(body=BODIES["forecast_chart"], targets=targets) == "forecast[4] "


@pytest.mark.skipif(not Path(CHROME).exists(), reason="needs Chrome")
def test_choosing_a_case_shows_its_figures_and_picks_no_part() -> None:
    page = render(spec=spec(body=BODIES["scenarios"]), data=DATA, form="live")
    # Keys and pointer both change the radio, and the page answers the change event.
    measure = (
        "var visible=function(){return Array.from(document.querySelectorAll('.case'))"
        ".filter(function(p){return getComputedStyle(p).display!=='none';});};"
        "var before=visible().length;"
        "var radio=document.querySelectorAll('.cases input')[1];radio.click();"
        "var shown=visible();"
        "if(before!==1)return 'before:'+before;"
        "return shown.length+':'+shown[0].getAttribute('data-case')+':'"
        "+shown[0].querySelector('.stat-value').textContent;"
    )
    assert _at_widths(page=page, measure=measure) == sorted(f"{w}:1:1:CHF 3'000.00" for w in WIDTHS)
    radio = "document.querySelectorAll('.cases input')[1]"
    assert _clicks(body=BODIES["scenarios"], targets=[radio]) == ""
