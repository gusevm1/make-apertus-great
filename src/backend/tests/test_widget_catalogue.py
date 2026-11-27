import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import BadRequestError
from app.features.widgets.catalogue import render as render_module
from app.features.widgets.catalogue.prompts import NOT_COMPONENTS, PROMPTS, catalogue_prompt
from app.features.widgets.catalogue.render import Form, fallback, render
from app.features.widgets.catalogue.schemas import COMPONENTS, WidgetSpec
from app.features.widgets.catalogue.values import display, resolve

SNAPSHOTS = Path(__file__).with_name("snapshots") / "widget_catalogue"
CHROME = os.environ.get(
    "CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
WIDTHS = (360, 440, 1000)
CHARTS = ("bar_chart", "line_chart", "area_chart", "comparison", "donut")
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
    "goals": [{"name": "Japan 2027", "saved_chf": 9000.0, "goal_chf": 12000.0}],
}
BODIES: dict[str, dict[str, Any]] = {
    "kpi": {
        "type": "kpi",
        "label": "October",
        "value": "months[1].total_chf",
        "compare": "months[0].total_chf",
        "compare_label": "September",
    },
    "stat_row": {
        "type": "stat_row",
        "stats": [
            {"label": "September", "value": "months[0].total_chf"},
            {"label": "October", "value": "months[1].total_chf"},
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


def test_the_total_sits_under_its_amount_column() -> None:
    swapped = {**BODIES["table"], "columns": ["amount_chf", "payee"]}
    page = render(spec=spec(body=swapped), data=DATA, form="static")
    total = re.search(r"<tfoot>.*?</tfoot>", page, re.DOTALL)
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


def test_a_comparison_needs_its_period_field() -> None:
    with pytest.raises(ValidationError):
        spec(body={key: value for key, value in BODIES["comparison"].items() if key != "series"})


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
    assert "stats (list of {label, value: path into DATA}, 2 to 4 items)" in prompt
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
        + [{"type": "stack", "children": [BODIES[name] for name in CHARTS]}],
    }
    page = render(spec=spec(body=body), data=DATA, form=form)
    probe = (
        "<script>setTimeout(function(){var r=document.documentElement;"
        "parent.postMessage({probe: true, width: innerWidth, "
        "overflow: r.scrollWidth > r.clientWidth + 1, "
        "charts: document.querySelectorAll('.chart-area svg').length}, '*')}, 2000)</script></body>"
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
            "seen.push(e.data.width+':'+e.data.overflow+':'+e.data.charts);document.body.setAttribute('data-seen',seen.sort().join(','))})</script></body>"
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
    # Every chart drawn, by the browser (live) or as SVG from the server (static).
    expected = sorted(f"{w}:false:{len(CHARTS)}" for w in WIDTHS)
    assert sorted(seen.group(1).split(",")) == expected


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
def test_clicking_a_static_bar_reports_its_row_and_bookings() -> None:
    bar = "document.querySelector('.chart-area [aria-label$=\"(months[1])\"]')"
    assert _clicks(body=BODIES["bar_chart"], targets=[bar], form="static") == "months[1] BK-03"
