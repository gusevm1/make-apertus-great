from datetime import date
from decimal import Decimal

import pytest

from app.features.ledger.schemas import LedgerRow
from evals.widgets.data import last_full_months, monthly_spending
from evals.widgets.page import (
    CSP,
    Edit,
    EditError,
    Edits,
    Scene,
    Shape,
    apply_edits,
    figure_problems,
    page,
    preview,
    render_scene,
    strip_fence,
)

DATA = {
    "months": [{"label": "2026-10", "total_chf": 9752.52, "booking_ids": ["BK-1", "BK-2"]}],
    "share": 0.125,
}


def test_csp_comes_before_data_and_code() -> None:
    html = page(body="<script>alert(1)</script>", data=DATA)
    assert html.index(CSP) < html.index("window.DATA") < html.index("alert(1)")


def test_data_cannot_close_its_script() -> None:
    html = page(body="", data={"text": "</script><script>alert(1)</script>"})
    assert "</script><script>alert(1)" not in html


# The matching rules themselves are tested with the chat's figure check in
# test_figure_checks_service.py; these only pin how a widget page is fed to it.
def test_figures_from_data_pass_the_chat_check() -> None:
    texts = ["Ausgaben Oktober", "CHF 9 752.52", "12.5 %"]
    assert figure_problems(texts=texts, data=DATA, request="") == []


def test_invented_figure_is_reported() -> None:
    problems = figure_problems(texts=["Total CHF 1'234.00"], data=DATA, request="")
    assert len(problems) == 1
    assert "1'234.00" in problems[0]


def test_broken_values_come_first() -> None:
    problems = figure_problems(texts=["CHF NaN", "undefined"], data=DATA, request="")
    assert problems == ["NaN", "undefined"]


def test_edits_apply_only_when_they_match_once() -> None:
    code = "<rect fill='#2E6B66'/><rect fill='#2E6B66' id='oct'/>"
    edited = apply_edits(
        code=code, edits=Edits(edits=[Edit(old="id='oct'", new="id='oct' class='red'")])
    )
    assert "class='red'" in edited
    with pytest.raises(EditError):
        apply_edits(code=code, edits=Edits(edits=[Edit(old="fill='#2E6B66'", new="fill='red'")]))


def test_shapes_escape_model_text() -> None:
    scene = Scene(
        width=600,
        height=100,
        shapes=[Shape(kind="text", x=1, y=2, text="<script>x</script>", fill='"><b')],
    )
    svg = render_scene(scene=scene)
    assert "<script>" not in svg
    assert '"><b' not in svg


def test_preview_shortens_booking_ids() -> None:
    assert preview(value={"booking_ids": list(range(10))}) == {"booking_ids": [0, 1, 2]}


def test_strip_fence() -> None:
    assert strip_fence(text="```html\n<div></div>\n```") == "<div></div>"
    assert strip_fence(text="<div></div>") == "<div></div>"


def _row(day: str, amount: str, booking_id: str) -> LedgerRow:
    return LedgerRow(
        source="booking",
        id=booking_id,
        account_id="ACC-PRIV",
        date=date.fromisoformat(day),
        amount_chf=Decimal(amount),
        text="Migros",
        kind="spending",
    )


def test_last_full_months_end_before_today() -> None:
    assert last_full_months(today=date(2026, 11, 27), count=3) == ["2026-08", "2026-09", "2026-10"]
    assert last_full_months(today=date(2026, 1, 5), count=2) == ["2025-11", "2025-12"]


def test_monthly_spending_is_positive_and_names_its_bookings() -> None:
    rows = [_row("2026-10-03", "-20.50", "BK-1"), _row("2026-10-20", "-9.50", "BK-2")]
    result = monthly_spending(rows=rows, months=["2026-09", "2026-10"])
    assert result["months"] == [
        {"label": "2026-09", "total_chf": 0.0, "booking_ids": []},
        {"label": "2026-10", "total_chf": 30.0, "booking_ids": ["BK-1", "BK-2"]},
    ]
    assert result["total_chf"] == 30.0
