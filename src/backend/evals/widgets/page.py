"""Widget pages for the benchmark: assembly, shapes, templates, code edits and the figure check."""

import html
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment
from markupsafe import Markup
from pydantic import BaseModel, Field

from app.features.figure_checks.service import FigureCheckService

# Blocks fetches, CDNs, forms and <base>. It doesn't stop the page from navigating itself to a URL
# that carries DATA; no CSP or sandbox flag here does.
CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; font-src data:; form-action 'none'; base-uri 'none'"
)
BRIDGE = (Path(__file__).with_name("bridge.js")).read_text(encoding="utf-8")
PREVIEW_ITEMS = 20
PREVIEW_IDS = 3

_FENCE = re.compile(r"\s*```[a-zA-Z]*\n(.*?)\n?```\s*", re.DOTALL)
# What a script shows when it read a value that isn't there.
_BROKEN = re.compile(r"\b(?:NaN|undefined|Infinity|null)\b")


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


class TemplateRefusedError(Exception):
    pass


def fill_template(template: str, data: dict[str, Any], request: str) -> str:
    """Render a model's Jinja template with DATA in the sandbox; refuse numbers it typed itself."""
    typed = FigureCheckService().check_figures(
        answer=template_text(template=template), sources=[request]
    )
    if typed is not None and not typed.passed:
        raise TemplateRefusedError(f"numbers of its own: {typed.detail}")
    try:
        return _TEMPLATES.from_string(template).render(DATA=data)
    # A filter or expression of the model's can fail with any of these on the wrong input.
    except (TemplateError, ValueError, TypeError, ArithmeticError, LookupError) as error:
        raise TemplateRefusedError(f"template error: {error}") from error


def template_text(template: str) -> str:
    """The template's visible text: without placeholders, tags, styles and scripts."""
    text = _TEMPLATE_CODE.sub(" ", template)
    return html.unescape(_TAG.sub(" ", _STYLE_OR_SCRIPT.sub(" ", text)))


def _chf(value: float) -> Markup:
    # Markup, so autoescape keeps the apostrophe of "CHF 1'234.50" as it is.
    return Markup(f"CHF {value:,.2f}".replace(",", "'"))


def _date(value: str) -> str:
    text = str(value)[:10]
    # DATA labels months as 2026-05; they show as 05.2026.
    if _MONTH.fullmatch(text) is not None:
        return f"{text[5:7]}.{text[:4]}"
    return date.fromisoformat(text).strftime("%d.%m.%Y")


def _scale(value: float, maximum: float, length: float) -> float:
    return 0.0 if maximum == 0 else value / maximum * length


# Immutable: a template can't change DATA, read attributes starting with _ or reach Python
# internals. Strict: a misspelt field fails instead of drawing nothing.
_TEMPLATES = ImmutableSandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
_TEMPLATES.filters["chf"] = _chf
_TEMPLATES.filters["date"] = _date
# Both forms, since models write scale(v, m, l) as often as v | scale(m, l).
_TEMPLATES.globals["scale"] = _scale
_TEMPLATES.filters["scale"] = _scale
_TEMPLATE_CODE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.DOTALL)
_STYLE_OR_SCRIPT = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]*>")
_MONTH = re.compile(r"\d{4}-\d{2}")


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


def figure_problems(texts: list[str], data: dict[str, Any], request: str) -> list[str]:
    """Values such as NaN, and the chat's own figure check of the page against DATA."""
    broken = [match.group(0) for text in texts for match in _BROKEN.finditer(text)]
    check = FigureCheckService().check_figures(
        answer="\n".join(texts), sources=[json.dumps(data, ensure_ascii=False), request]
    )
    if check is None or check.passed:
        return broken
    return [*broken, check.detail if check.detail is not None else "figures not found"]


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
