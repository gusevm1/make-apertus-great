import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from app.core.provenance import Check

NOT_FOUND_LISTED = 10
# The prompt files that instruct the model; a sentence of theirs never belongs in an answer.
INSTRUCTION_PROMPTS = ("tool_calls", "boards", "conversations")
# Shorter sentences are common enough to appear in an answer by chance.
PROMPT_SENTENCE_MIN_CHARS = 80
# "CHF ?", or "CHF will remain" where the corrector dropped the number; "in CHF per" is a unit.
_OPEN_AMOUNT = re.compile(r"(?:CHF|Fr\.)\s*\?|(?<!\bin )(?<!\bof )\b(?:CHF|Fr\.) +(?=[a-zäöü])")
_SENTENCE_END = re.compile(r"(?<=[.!?:])\s+|\n+")
_SPACES = re.compile(r"\s+")
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
    # A Swiss day without its year, such as 23.12., never after a currency.
    r"|(?<!CHF )(?<!CHF)(?<![\d.'\u2019])(?:0?[1-9]|[12]\d|3[01])\.(?:0?[1-9]|1[0-2])\.(?!\d)"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)\s+(?:of\s+)?(?:{_MONTHS})\b"
    # A day of the month on its own, such as "before the 23rd".
    r"|\bthe \d{1,2}(?:st|nd|rd|th)\b"
    # Without its last dot only after a word that names a day: "on 07.12 at".
    r"|\b(?:on|by|until|from|am|bis|vom|ab) (?:0?[1-9]|[12]\d|3[01])\.(?:0?[1-9]|1[0-2])(?![\d.])"
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
_LAST_MONTH = re.compile(
    r"\b(?:last|previous) month\b|\b(?:letzten|vergangenen|im vergangenen) Monat\b|\bVormonat",
    re.IGNORECASE,
)
_THIS_MONTH = re.compile(r"\bthis month\b|\bdiesen Monat\b|\bdiesem Monat\b", re.IGNORECASE)
# A span around a month, a year or an average per month: the month is not the figure's period.
_SPAN_WORDS = re.compile(
    rf"\b(?:seit|since|ab|from|bis|to|until|vor|before|nach|after)\s+(?:(?:the\s+)?"
    rf"(?:end|start|Ende|Anfang)\s+(?:of\s+)?)?(?:{_MONTHS}|\d)"
    r"|\b(?:zwischen|between|seit|since|bis|bisher|until|through|so far|to date|year|Jahr\w*"
    r"|per month|pro Monat|monthly|monatlich|average)\b|Durchschnitt|durchschnittlich",
    re.IGNORECASE,
)
# Where the words that belong to a figure end: a sentence end, a semicolon or a new line.
_CLAUSE_END = re.compile(r"[.!?;]\s|\n")
# A minus touching the number or after its currency; a list dash and an en dash are no sign.
_MINUS_BEFORE = re.compile(r"(?<![\w.,])[-\u2212\u2011]$|CHF\s?[-\u2212\u2011]\s?$")
# Sums of money moved, which the ledger signs negative for money out.
_SUM_KEYS = {
    "money_out_chf",
    "money_in_chf",
    "provisional_out_chf",
    "provisional_in_chf",
    "average_out_chf",
    "average_in_chf",
    "spent_chf",
}
_MONTH_KEY = re.compile(r"\d{4}-\d{2}")


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

    def check_complete(self, answer: str) -> Check | None:
        """Whether the answer leaves an amount open or copies a sentence of our prompts."""
        reasons = []
        if _OPEN_AMOUNT.search(answer) is not None:
            reasons.append("an amount left open (CHF ?)")
        flat = _flat(text=answer)
        if any(sentence in flat for sentence in _prompt_sentences()):
            reasons.append("a sentence of the instructions")
        if not reasons:
            return None
        return Check(name="answer_complete", passed=False, detail="; ".join(reasons))

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

    def check_context(
        self, answer: str, calls: list[tuple[dict[str, Any], dict[str, Any]]], today: date
    ) -> Check | None:
        """Whether a figure tied to a month or a minus fits the (arguments, result) holding it."""
        leaves = [
            leaf
            for arguments, result in calls
            for leaf in _leaves(value=result, key="", period=_call_period(arguments=arguments))
        ]
        blanked = _without_dates(text=answer)
        judged = 0
        flagged: dict[str, list[str]] = {}
        for figure in _checked_figures(text=answer):
            holding = [leaf for leaf in leaves if _found(figure=figure, values={abs(leaf.value)})]
            if not holding:
                continue
            reasons = _context_reasons(
                figure=figure, holding=holding, answer=answer, blanked=blanked, today=today
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


# First and last day; None is open at that end.
Period = tuple[date | None, date | None]
Month = tuple[date, date]


@dataclass(frozen=True)
class _Leaf:
    key: str
    value: Decimal
    period: Period | None  # None when the result does not say which period it covers


def _call_period(arguments: dict[str, Any]) -> Period | None:
    if arguments.get("date_from") is None and arguments.get("date_to") is None:
        return None
    try:
        return _optional_date(value=arguments.get("date_from")), _optional_date(
            value=arguments.get("date_to")
        )
    except (TypeError, ValueError):
        return None


def _optional_date(value: Any) -> date | None:
    return None if value is None else date.fromisoformat(value)


# The nearest of a month row, a single movement (no period) or a result's own dates wins.
def _leaves(value: Any, key: str, period: Period | None) -> list[_Leaf]:
    if isinstance(value, dict):
        period = _own_period(row=value, period=period)
        return [
            leaf
            for name, item in value.items()
            for leaf in _leaves(value=item, key=name, period=period)
        ]
    if isinstance(value, list):
        return [leaf for item in value for leaf in _leaves(value=item, key=key, period=period)]
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return []
    try:
        return [_Leaf(key=key, value=Decimal(str(value)), period=period)]
    except InvalidOperation:
        return []


def _own_period(row: dict[str, Any], period: Period | None) -> Period | None:
    month = row.get("month")
    if isinstance(month, str) and _MONTH_KEY.fullmatch(month):
        return _month_period(year=int(month[:4]), month=int(month[5:]))
    if "date" in row:
        return None
    if "date_from" in row and "date_to" in row:
        try:
            return _optional_date(value=row["date_from"]), _optional_date(value=row["date_to"])
        except (TypeError, ValueError):
            return None
    return period


def _month_period(year: int, month: int) -> Month:
    first = date(year, month, 1)
    return first, date(year, month, monthrange(year, month)[1])


# None when the answer gives no month or minus to judge the figure by.
def _context_reasons(
    figure: Figure, holding: list[_Leaf], answer: str, blanked: str, today: date
) -> list[str] | None:
    reasons: list[str] = []
    is_judged = False
    month = _named_month(figure=figure, answer=answer, blanked=blanked, today=today)
    # A result that says nothing about its period cannot tell the month apart.
    if month is not None and all(leaf.period is not None for leaf in holding):
        is_judged = True
        if not any(_within(period=leaf.period, month=month) for leaf in holding):
            reasons.append("from another period")
    if _MINUS_BEFORE.search(answer[max(0, figure.start - CURRENCY_BEFORE_CHARS) : figure.start]):
        is_judged = True
        if all(leaf.key in _SUM_KEYS for leaf in holding):
            reasons.append("a sum written with a minus")
    return reasons if is_judged else None


# The one month the figure's clause names; None for none, several or a span around a month.
def _named_month(figure: Figure, answer: str, blanked: str, today: date) -> Month | None:
    ends = [match.end() for match in _CLAUSE_END.finditer(blanked, 0, figure.start)]
    start = ends[-1] if ends else 0
    after = _CLAUSE_END.search(blanked, figure.start)
    clause = answer[start : len(answer) if after is None else after.start()]
    if _SPAN_WORDS.search(clause):
        return None
    days = [match.span() for match in _DAY_DATES.finditer(clause)]
    months: set[Month] = set()
    for match in _MONTH_NAMED.finditer(clause):
        if any(first <= match.start() < last for first, last in days):
            continue
        number = _MONTH_NUMBERS[match["name"].lower()[:3]]
        year = int(match["year"]) if match["year"] is not None else None
        if year is None:
            year = today.year if number <= today.month else today.year - 1
        months.add(_month_period(year=year, month=number))
    if _LAST_MONTH.search(clause):
        last_day = today.replace(day=1) - timedelta(days=1)
        months.add(_month_period(year=last_day.year, month=last_day.month))
    if _THIS_MONTH.search(clause):
        months.add(_month_period(year=today.year, month=today.month))
    return next(iter(months)) if len(months) == 1 else None


def _within(period: Period | None, month: Month) -> bool:
    if period is None:
        return False
    first, last = period
    return first is not None and last is not None and month[0] <= first and last <= month[1]


def _flat(text: str) -> str:
    return _SPACES.sub(" ", text).strip().casefold()


@cache
def _prompt_sentences() -> frozenset[str]:
    features = Path(__file__).parents[1]
    sentences = set()
    for feature in INSTRUCTION_PROMPTS:
        prompts = yaml.safe_load((features / feature / "prompts.yaml").read_text(encoding="utf-8"))
        for value in _strings(value=prompts):
            for sentence in _SENTENCE_END.split(value):
                flat = _flat(text=sentence)
                # A sentence with a placeholder is filled in before it is sent, never verbatim.
                if len(flat) >= PROMPT_SENTENCE_MIN_CHARS and "{" not in flat:
                    sentences.add(flat)
    return frozenset(sentences)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(value=item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(value=item)]
    return []
