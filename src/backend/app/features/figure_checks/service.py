import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.provenance import Check

NOT_FOUND_LISTED = 10
_MONTHS = (
    "jan(?:uary|uar)?|feb(?:ruary|ruar)?|m(?:ar(?:ch)?|\u00e4rz|aerz)|apr(?:il)?|ma[iy]|jun[ei]?"
    "|jul[iy]?|aug(?:ust)?|sep(?:t(?:ember)?)?|o[ck]t(?:ober)?|nov(?:ember)?|de[cz](?:ember)?"
)
# Dates are no figures: 2026-10-31, 31.10.2026, 31 October, 31. Oktober, October 31, October 2026.
_DATES = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}\b"
    rf"|\b\d{{1,2}}\.?\s+(?:{_MONTHS})\b|\b(?:{_MONTHS})\b\.?\s+\d{{1,4}}\b",
    re.IGNORECASE,
)
# Thousands written with an apostrophe or a typographic space, never with a plain space.
_THOUSANDS = "'\u2019\u00a0\u202f\u2009"
# 2'916.35, 2 916.35 with a narrow space, 114,599.33, 2916.35, 0,95, 12 %, 9.8k
_NUMBER = re.compile(
    rf"(?<![\w.,{_THOUSANDS}])(\d{{1,3}}(?:[{_THOUSANDS}]\d{{3}})+"
    r"|\d{1,3}(?:,\d{3})+(?![\d,])|\d+)"
    r"(?:[.,](\d+))?(\s?%|k\b)?"
)


@dataclass(frozen=True)
class Figure:
    text: str
    value: Decimal
    decimals: int
    thousands: bool


class FigureCheckService:
    def check_figures(self, answer: str, sources: list[str]) -> Check | None:
        """Whether every number in the answer is in the sources; None when it has none."""
        figures = [figure for figure in _figures(text=answer) if not _is_count_or_year(figure)]
        if not figures:
            return None
        values = {figure.value for source in sources for figure in _figures(text=source)}
        missing = list(dict.fromkeys(f.text for f in figures if not _found(f, values=values)))
        found = len(figures) - len([f for f in figures if f.text in missing])
        detail = f"{found} of {len(figures)} found"
        if missing:
            detail += "; not found: " + ", ".join(missing[:NOT_FOUND_LISTED])
        return Check(name="figures_found", passed=not missing, detail=detail)


def _figures(text: str) -> list[Figure]:
    figures: list[Figure] = []
    for match in _NUMBER.finditer(_DATES.sub(" ", text)):
        whole, fraction, suffix = match.group(1), match.group(2), match.group(3) or ""
        digits = re.sub(f"[,{_THOUSANDS}]", "", whole)
        value = Decimal(digits if fraction is None else f"{digits}.{fraction}")
        figures.append(
            Figure(
                text=match.group(0).strip(),
                value=value,
                decimals=0 if fraction is None else len(fraction),
                thousands=suffix.strip() == "k",
            )
        )
    return figures


def _is_count_or_year(figure: Figure) -> bool:
    # ponytail: single digits are counts and list numbers ("3 months", "1."); years read as dates.
    if figure.decimals > 0 or figure.thousands or figure.text.endswith("%"):
        return False
    return figure.value < 10 or 1900 <= figure.value <= 2100


def _found(figure: Figure, values: set[Decimal]) -> bool:
    step = Decimal(1).scaleb(-figure.decimals)
    scale = Decimal(1000) if figure.thousands else Decimal(1)
    return any(
        (value / scale).quantize(step, rounding=ROUND_HALF_UP) == figure.value for value in values
    )
