import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

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
# The model also writes the hyphens of a date as the non-breaking or other Unicode hyphens.
_HYPHEN = "[-\u2010\u2011\u2012\u2013]"
# Dates are no figures: 2026-10-31, 31.10.2026, 31 October, 31. Oktober, October 31, October 2026.
_DATES = re.compile(
    rf"\b\d{{4}}{_HYPHEN}\d{{2}}{_HYPHEN}\d{{2}}\b|\b\d{{1,2}}\.\d{{1,2}}\.\d{{2,4}}\b"
    rf"|\b\d{{1,2}}\.?\s+(?:{_MONTHS})\b|\b(?:{_MONTHS})\b\.?\s+(?:\d{{4}}|\d{{1,2}})\b"
)
# Only dates with a day: 2026-12-15, 15.12.2026, 15 December, 15. Dezember, December 15.
_DAY_DATES = re.compile(
    rf"\b(?P<iso_year>\d{{4}}){_HYPHEN}(?P<iso_month>\d{{2}}){_HYPHEN}(?P<iso_day>\d{{2}})(?!\d)"
    rf"|\b(?P<dot_day>\d{{1,2}})\.(?P<dot_month>\d{{1,2}})\.(?P<dot_year>\d{{2,4}})\b"
    rf"|\b(?P<day>\d{{1,2}})\.?\s+(?P<month>{_MONTHS})\b(?:\s+(?P<year>\d{{4}})\b)?"
    rf"|\b(?P<month_first>{_MONTHS})\.?\s+(?P<day_after>\d{{1,2}})\b(?:,?\s+(?P<year_after>\d{{4}})\b)?"
)
_MONTH_NUMBERS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "m\u00e4r": 3,
    "mae": 3,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "okt": 10,
    "oct": 10,
    "nov": 11,
    "dez": 12,
    "dec": 12,
}
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
# A month named in the answer, with the year when one follows it.
_MONTH_NAMED = re.compile(rf"\b(?P<name>{_MONTHS})\b\.?(?:\s+(?P<year>\d{{4}})\b)?")
# Where the words that belong to a figure end: a sentence end, a semicolon or a new line.
_CLAUSE_END = re.compile(r"[.!?;]\s|\n")
# A minus right before the number or after its currency; a list's "- CHF 430.05" is no sign.
_MINUS_BEFORE = re.compile(r"(?<![\w.,])[-\u2212\u2011\u2013]\s?$|CHF\s?[-\u2212\u2011\u2013]\s?$")
# Fields of money moved; the ledger writes money out as negative, the answer as spent.
MOVED_KEYS = {
    "amount_chf",
    "money_out_chf",
    "money_in_chf",
    "provisional_out_chf",
    "provisional_in_chf",
    "average_out_chf",
    "average_in_chf",
}


@dataclass(frozen=True)
class Figure:
    text: str
    start: int  # where the number starts in the text, for the words around it
    value: Decimal
    decimals: int
    is_kilo: bool  # written with a k, such as 9.8k
    is_percent: bool
    is_amount: bool  # a currency next to it, or written with a thousands separator


class FigureCheckService:
    def check_figures(self, answer: str, sources: list[str]) -> Check | None:
        """Whether every number in the answer is in the sources; None when it has none."""
        figures = _checked_figures(text=answer)
        if not figures:
            return None
        missing = _missing(figures=figures, sources=sources)
        found = len(figures) - len([f for f in figures if f.text in missing])
        detail = f"{found} of {len(figures)} found"
        if missing:
            detail += "; not found: " + ", ".join(missing[:NOT_FOUND_LISTED])
        return Check(name="figures_found", passed=not missing, detail=detail)

    def missing_figures(self, answer: str, sources: list[str]) -> list[str]:
        """The figures of the answer that no source holds, as the answer writes them."""
        return _missing(figures=_checked_figures(text=answer), sources=sources)

    def check_dates(
        self, answer: str, results: list[dict[str, Any]], texts: list[str]
    ) -> Check | None:
        """Whether each line with one amount and one date has a source row with both."""
        rows = [_Row.of(text=row) for result in results for row in _result_rows(value=result)]
        rows += [_Row.of(text=line) for text in texts for line in text.splitlines()]
        dated = [line.strip() for line in answer.splitlines() if _amount_and_date(line=line)]
        if not dated:
            return None
        missing = [line for line in dated if not _has_row(line=line, rows=rows)]
        detail = f"{len(dated) - len(missing)} of {len(dated)} matched"
        if missing:
            detail += "; not matched: " + " | ".join(missing[:NOT_FOUND_LISTED])
        return Check(name="dates_match", passed=not missing, detail=detail)

    def check_context(self, answer: str, results: list[Any]) -> Check | None:
        """Whether a figure tied to a month or written with a minus fits the results holding it."""
        leaves = [leaf for result in results for leaf in _leaves(value=result, key="", month=None)]
        blanked = _without_dates(text=answer)
        judged = 0
        flagged: dict[str, list[str]] = {}
        for figure in _checked_figures(text=answer):
            holding = [leaf for leaf in leaves if _found(figure=figure, values={abs(leaf.value)})]
            if not holding:
                continue
            reasons = _context_reasons(
                figure=figure, holding=holding, answer=answer, blanked=blanked
            )
            if reasons is None:
                continue
            judged += 1
            for reason in reasons:
                flagged.setdefault(reason, []).append(figure.text)
        if judged == 0:
            return None
        flagged_texts = {text for texts in flagged.values() for text in texts}
        detail = f"{judged - len(flagged_texts)} of {judged} fit"
        for reason, texts in flagged.items():
            detail += f"; {reason}: " + ", ".join(dict.fromkeys(texts))
        return Check(name="figures_in_context", passed=not flagged, detail=detail)

    def has_figure(self, answer: str, value: Decimal) -> bool:
        """Whether the answer writes this value, rounded as the answer rounds it."""
        return any(
            _found(figure=figure, values={value})
            for figure in _figures(text=answer)
            if not _is_count_or_year(figure=figure)
        )


# (year or None when not written, month, day)
DayDate = tuple[int | None, int, int]


@dataclass(frozen=True)
class _Row:
    values: set[Decimal]
    dates: set[DayDate]

    @classmethod
    def of(cls, text: str) -> "_Row":
        return cls(values={f.value for f in _figures(text=text)}, dates=_day_dates(text=text))


def _figures(text: str) -> list[Figure]:
    text = _without_dates(text=text)
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
                start=match.start(),
                value=Decimal(digits if fraction is None else f"{digits}.{fraction}"),
                decimals=0 if fraction is None else len(fraction),
                is_kilo=suffix == "k",
                is_percent=suffix == "%",
                is_amount=has_currency or digits != whole,
            )
        )
    return figures


# Blanked with as many spaces, so a figure's position is the same in the answer.
def _without_dates(text: str) -> str:
    return _DATES.sub(lambda match: " " * len(match.group(0)), text)


def _checked_figures(text: str) -> list[Figure]:
    return [figure for figure in _figures(text=text) if not _is_count_or_year(figure)]


def _missing(figures: list[Figure], sources: list[str]) -> list[str]:
    values = {figure.value for source in sources for figure in _figures(text=source)}
    return list(dict.fromkeys(f.text for f in figures if not _found(f, values=values)))


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


# Each dict of a tool result is one row of its own plain values.
def _result_rows(value: Any) -> list[str]:
    if isinstance(value, list):
        return [row for item in value for row in _result_rows(value=item)]
    if not isinstance(value, dict):
        return []
    plain = [str(item) for item in value.values() if isinstance(item, str | int | float)]
    nested = [row for item in value.values() for row in _result_rows(value=item)]
    return [" ".join(plain), *nested] if plain else nested


def _day_dates(text: str) -> set[DayDate]:
    dates: set[DayDate] = set()
    for match in _DAY_DATES.finditer(text):
        parts = {name: part for name, part in match.groupdict().items() if part is not None}
        year = parts.get("iso_year") or parts.get("dot_year") or parts.get("year")
        year = year or parts.get("year_after")
        day = int(
            parts.get("iso_day") or parts.get("dot_day") or parts.get("day") or parts["day_after"]
        )
        month_name = parts.get("month") or parts.get("month_first")
        if month_name is None:
            month = int(parts.get("iso_month") or parts["dot_month"])
        else:
            month = _MONTH_NUMBERS[month_name.lower()[:3]]
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        if year is not None and len(year) == 2:
            year = f"20{year}"
        dates.add((None if year is None else int(year), month, day))
    return dates


def _amounts(line: str) -> list[Figure]:
    return [f for f in _figures(text=line) if not _is_count_or_year(f) and not f.is_percent]


def _amount_and_date(line: str) -> bool:
    return len(_amounts(line=line)) == 1 and len(_day_dates(text=line)) == 1


def _same_day(written: DayDate, source: DayDate) -> bool:
    if written[0] is not None and source[0] is not None and written[0] != source[0]:
        return False
    return written[1:] == source[1:]


def _has_row(line: str, rows: list[_Row]) -> bool:
    amount = _amounts(line=line)[0]
    (date,) = _day_dates(text=line)
    return any(
        _found(amount, values=row.values)
        and any(_same_day(written=date, source=row_date) for row_date in row.dates)
        for row in rows
    )


@dataclass(frozen=True)
class _Leaf:
    key: str
    value: Decimal
    month: str | None  # YYYY-MM of the month row it is in


def _leaves(value: Any, key: str, month: str | None) -> list[_Leaf]:
    if isinstance(value, dict):
        own = value.get("month")
        month = own if isinstance(own, str) and _MONTH_KEY.fullmatch(own) else month
        return [
            leaf
            for name, item in value.items()
            for leaf in _leaves(value=item, key=name, month=month)
        ]
    if isinstance(value, list):
        return [leaf for item in value for leaf in _leaves(value=item, key=key, month=month)]
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return []
    try:
        return [_Leaf(key=key, value=Decimal(str(value)), month=month)]
    except InvalidOperation:
        return []


_MONTH_KEY = re.compile(r"\d{4}-\d{2}")


# None when the answer gives no month or minus to judge the figure by.
def _context_reasons(
    figure: Figure, holding: list[_Leaf], answer: str, blanked: str
) -> list[str] | None:
    reasons: list[str] = []
    is_judged = False
    month = _named_month(figure=figure, answer=answer, blanked=blanked)
    if month is not None:
        is_judged = True
        if _other_month_only(month=month, holding=holding):
            reasons.append("from another month")
    if _MINUS_BEFORE.search(answer[max(0, figure.start - CURRENCY_BEFORE_CHARS) : figure.start]):
        is_judged = True
        if all(leaf.key in MOVED_KEYS for leaf in holding):
            reasons.append("money moved written with a minus")
    return reasons if is_judged else None


# The one month the figure's clause names, as (year or None, month); None for none or several.
def _named_month(figure: Figure, answer: str, blanked: str) -> tuple[int | None, int] | None:
    ends = [match.end() for match in _CLAUSE_END.finditer(blanked, 0, figure.start)]
    start = ends[-1] if ends else 0
    after = _CLAUSE_END.search(blanked, figure.start)
    clause = answer[start : len(answer) if after is None else after.start()]
    named = {
        (
            None if match["year"] is None else int(match["year"]),
            _MONTH_NUMBERS[match["name"].lower()[:3]],
        )
        for match in _MONTH_NAMED.finditer(clause)
    }
    if len({month for _, month in named}) != 1:
        return None
    years = {year for year, _ in named if year is not None}
    if len(years) > 1:
        return None
    return (next(iter(years), None), next(iter(named))[1])


def _other_month_only(month: tuple[int | None, int], holding: list[_Leaf]) -> bool:
    if any(leaf.month is None for leaf in holding):
        return False
    year, number = month
    return not any(
        int(leaf.month[5:7]) == number and (year is None or int(leaf.month[:4]) == year)
        for leaf in holding
        if leaf.month is not None
    )
