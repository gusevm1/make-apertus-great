import pytest

from evals.widgets.page import (
    CSP,
    Edit,
    EditError,
    Edits,
    Scene,
    Shape,
    apply_edits,
    missing_numbers,
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


@pytest.mark.parametrize("shown", ["CHF 9'752.52", "9’753", "9.8k", "12.5%", "9,752.52"])
def test_numbers_from_data_count_as_found(shown: str) -> None:
    assert missing_numbers(texts=[shown], data=DATA, request="") == []


def test_number_not_in_data_is_missing() -> None:
    assert missing_numbers(texts=["Total CHF 1'234.00"], data=DATA, request="") == ["1'234.00"]


def test_dates_years_and_request_numbers_are_skipped() -> None:
    texts = ["Oct 2026", "27.11.2026", "2026-10", "letzte 6 Monate"]
    assert missing_numbers(texts=texts, data=DATA, request="over the last 6 months") == []


def test_broken_values_count_as_missing() -> None:
    assert missing_numbers(texts=["CHF NaN", "undefined"], data=DATA, request="") == [
        "NaN",
        "undefined",
    ]


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
