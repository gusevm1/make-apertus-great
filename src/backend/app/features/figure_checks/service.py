import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.provenance import Check

NOT_FOUND_LISTED = 10
# A bare whole number below this is a count or a list number ("3 months", "1."), not a figure.
COUNTS_BELOW = 10
# A bare whole number in this range is a year.
YEARS = range(1900, 2101)
# Longer digit runs are references (a QR bill has 27 digits), never amounts.
MAX_DIGITS = 15
# How far before and after a number to look for its currency.
CURRENCY_BEFORE_CHARS = 6
CURRENCY_AFTER_CHARS = 12
# Capitalised, as German nouns and English months are written; lowercase "may" is no month.
_MONTHS = (
    "Jan(?:uary|uar)?|Feb(?:ruary|ruar)?|M(?:ar(?:ch)?|\u00e4rz|aerz)|Apr(?:il)?|Ma[iy]|Jun[ei]?"
    "|Jul[iy]?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|O[ck]t(?:ober)?|Nov(?:ember)?|De[cz](?:ember)?"
)
# Dates are no figures: 2026-10-31, 31.10.2026, 31 October, 31. Oktober, October 31, October 2026.
_DATES = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}\b"
    rf"|\b\d{{1,2}}\.?\s+(?:{_MONTHS})\b|\b(?:{_MONTHS})\b\.?\s+(?:\d{{4}}|\d{{1,2}})\b"
)
# Thousands written with an apostrophe or a typographic space, never with a plain space.
_THOUSANDS = "'\u2019\u00a0\u202f\u2009"
# 2'916.35, 2 916.35 with a narrow space, 114,599.33, 2916.35, 0,95, 12 %, 9.8k
_NUMBER = re.compile(
    rf"(?<![\w.,'\u2019])(?<!\d[{_THOUSANDS}])(\d{{1,3}}(?:[{_THOUSANDS}]\d{{3}})+"
    r"|\d{1,3}(?:,\d{3})+(?!\d|,\d)|\d+)"
    r"(?:[.,](\d+))?(\s?%|k\b)?"
)
# A currency next to a number makes it an amount, even when it looks like a year or a count.
_CURRENCY_BEFORE = re.compile(r"(?:CHF|Fr\.|EUR|USD|GBP|\u20ac|\$)\s*$")
_CURRENCY_AFTER = re.compile(r"^\s*(?:CHF|Franken|francs?|EUR|USD|GBP)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Figure:
    text: str
    value: Decimal
    decimals: int
    is_kilo: bool  # written with a k, such as 9.8k
    is_percent: bool
    is_amount: bool  # a currency next to it, or written with a thousands separator


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
    text = _DATES.sub(" ", text)
    figures: list[Figure] = []
    for match in _NUMBER.finditer(text):
        whole, fraction, suffix = match.group(1), match.group(2), (match.group(3) or "").strip()
        digits = re.sub(f"[,{_THOUSANDS}]", "", whole)
        if len(digits) + len(fraction or "") > MAX_DIGITS:
            continue
        has_currency = bool(
            _CURRENCY_BEFORE.search(
                text[max(0, match.start() - CURRENCY_BEFORE_CHARS) : match.start()]
            )
            or _CURRENCY_AFTER.search(text[match.end() : match.end() + CURRENCY_AFTER_CHARS])
        )
        figures.append(
            Figure(
                text=match.group(0).strip(),
                value=Decimal(digits if fraction is None else f"{digits}.{fraction}"),
                decimals=0 if fraction is None else len(fraction),
                is_kilo=suffix == "k",
                is_percent=suffix == "%",
                is_amount=has_currency or digits != whole,
            )
        )
    return figures


def _is_count_or_year(figure: Figure) -> bool:
    if figure.decimals > 0 or figure.is_kilo or figure.is_percent or figure.is_amount:
        return False
    return figure.value < COUNTS_BELOW or int(figure.value) in YEARS


def _found(figure: Figure, values: set[Decimal]) -> bool:
    step = Decimal(1).scaleb(-figure.decimals)
    scale = Decimal(1000) if figure.is_kilo else Decimal(1)
    # "12 %" may stand for 12 or for a ratio of 0.12 in the data.
    candidates = values | ({value * 100 for value in values} if figure.is_percent else set())
    return any(
        (value / scale).quantize(step, rounding=ROUND_HALF_UP) == figure.value
        for value in candidates
    )
