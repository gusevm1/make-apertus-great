"""Widget pages for the benchmark: assembly, the shapes variant, code edits and the number check."""

import html
import json
import re
from pathlib import Path
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, Field

# Blocks every request the page could make, so generated code can't send data out or load a CDN.
CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:"
)
BRIDGE = (Path(__file__).with_name("bridge.js")).read_text(encoding="utf-8")
PREVIEW_ITEMS = 20
PREVIEW_IDS = 3

_FENCE = re.compile(r"\s*```[a-zA-Z]*\n(.*?)\n?```\s*", re.DOTALL)
_DATE = re.compile(
    r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b|\b\d{4}-\d{2}(?:-\d{2})?\b|\b\d{1,2}/\d{4}\b"
)
# A k or M only scales the number when no other letter follows: "6 Months" is six, not six million.
_NUMBER = re.compile(r"-?\d(?:[\d'’,.]*\d)?(?:\s?(?:k|K|Mio\.?|M)(?![A-Za-z])|%)?")
_BROKEN = re.compile(r"\b(?:NaN|undefined|Infinity|null)\b")
_SCALES = {"k": 1e3, "K": 1e3, "M": 1e6, "Mio": 1e6, "Mio.": 1e6}


class Shape(BaseModel):
    kind: Literal["rect", "circle", "line", "path", "text"]
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    r: float | None = None
    x2: float | None = None
    y2: float | None = None
    d: str | None = None
    text: str | None = None
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = None
    font_size: float | None = None
    font_weight: Literal["normal", "bold"] | None = None
    anchor: Literal["start", "middle", "end"] | None = None


class Scene(BaseModel):
    width: float = Field(gt=0, le=2000)
    height: float = Field(gt=0, le=4000)
    shapes: list[Shape] = Field(max_length=400)


class Edit(BaseModel):
    old: str
    new: str


class Edits(BaseModel):
    edits: list[Edit] = Field(min_length=1, max_length=20)


class EditError(Exception):
    pass


def page(body: str, data: dict[str, Any], d3: str | None = None) -> str:
    """The widget page: the CSP first, then DATA, the bridge, d3 if given, then the code."""
    data_json = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    library = "" if d3 is None else f"<script>{d3}</script>"
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<script>window.DATA = {data_json};</script><script>{BRIDGE}</script>{library}"
        f'</head><body style="margin:0">{body}</body></html>'
    )


def strip_fence(text: str) -> str:
    match = _FENCE.fullmatch(text)
    return match.group(1) if match is not None else text.strip()


def render_scene(scene: Scene) -> str:
    parts = [_shape(shape=shape) for shape in scene.shapes]
    return (
        f'<svg viewBox="0 0 {scene.width:g} {scene.height:g}" width="100%" role="img" '
        f'style="font-family:system-ui;display:block">{"".join(parts)}</svg>'
    )


def apply_edits(code: str, edits: Edits) -> str:
    for edit in edits.edits:
        count = code.count(edit.old) if edit.old != "" else 0
        if count != 1:
            raise EditError(f"edit matches {count} times: {edit.old[:60]!r}")
        code = code.replace(edit.old, edit.new)
    return code


def preview(value: Any, key: str = "") -> Any:
    """DATA as the model sees it: long lists shortened, so the prompt stays small."""
    if isinstance(value, dict):
        return {name: preview(value=item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        limit = PREVIEW_IDS if key == "booking_ids" else PREVIEW_ITEMS
        return [preview(value=item) for item in value[:limit]]
    return value


def missing_numbers(texts: list[str], data: dict[str, Any], request: str) -> list[str]:
    """Numbers the page shows that are not in DATA or the request, and values such as NaN."""
    allowed = [abs(number) for number in _data_numbers(value=data)]
    allowed += [abs(number.value) * number.scale for number in _numbers(text=request)]
    broken = [match.group(0) for text in texts for match in _BROKEN.finditer(text)]
    return broken + [
        number.token
        for text in texts
        for number in _numbers(text=text)
        if not any(_shows(allowed=candidate, shown=number) for candidate in allowed)
    ]


class Shown(NamedTuple):
    value: float
    decimals: int
    scale: float
    is_percent: bool
    token: str


def _shows(allowed: float, shown: Shown) -> bool:
    # 12.5% may come from 12.5 or from 0.125 in DATA.
    candidates = (allowed, allowed * 100) if shown.is_percent else (allowed,)
    target = round(abs(shown.value), shown.decimals)
    return any(round(candidate / shown.scale, shown.decimals) == target for candidate in candidates)


def _numbers(text: str) -> list[Shown]:
    found = []
    for match in _NUMBER.finditer(_DATE.sub(" ", text)):
        shown = _parse(token=match.group(0))
        if shown is not None:
            found.append(shown)
    return found


def _parse(token: str) -> Shown | None:
    suffix = re.search(r"\s?(k|K|Mio\.?|M|%)$", token)
    digits = token[: suffix.start()] if suffix is not None else token
    digits = digits.replace("'", "").replace("’", "")
    digits = re.sub(r",(?=\d{3}(?!\d))", "", digits).replace(",", ".")
    if digits.count(".") > 1:
        digits = digits.replace(".", "")
    try:
        value = float(digits)
    except ValueError:
        return None
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    if suffix is None and decimals == 0 and 1990 <= value <= 2100:
        return None  # a year
    unit = None if suffix is None else suffix.group(1)
    scale = 1.0 if unit is None or unit == "%" else _SCALES[unit]
    return Shown(value=value, decimals=decimals, scale=scale, is_percent=unit == "%", token=token)


def _data_numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in _data_numbers(value=item)]
    if isinstance(value, list):
        return [number for item in value for number in _data_numbers(value=item)]
    if isinstance(value, str):
        # A number inside a DATA text, such as the account in "Depot 0418-2210.01", is DATA too.
        return [number.value * number.scale for number in _numbers(text=value)]
    return []


def _shape(shape: Shape) -> str:
    attributes = {
        "x": shape.x,
        "y": shape.y,
        "width": shape.width,
        "height": shape.height,
        "r": shape.r,
        "d": shape.d,
        "fill": shape.fill,
        "stroke": shape.stroke,
        "stroke-width": shape.stroke_width,
        "font-size": shape.font_size,
        "font-weight": shape.font_weight,
        "text-anchor": shape.anchor,
    }
    if shape.kind == "circle":
        attributes |= {"cx": attributes.pop("x"), "cy": attributes.pop("y")}
    if shape.kind == "line":
        attributes |= {
            "x1": attributes.pop("x"),
            "y1": attributes.pop("y"),
            "x2": shape.x2,
            "y2": shape.y2,
        }
    rendered = " ".join(
        f'{name}="{html.escape(str(value), quote=True)}"'
        for name, value in attributes.items()
        if value is not None
    )
    if shape.kind == "text":
        return f"<text {rendered}>{html.escape(shape.text or '')}</text>"
    return f"<{shape.kind} {rendered}/>"
