import json
from datetime import date

import pytest

from app.core.provenance import Check
from app.features.figure_checks.service import FigureCheckService

RESULT = json.dumps({"total_chf": 2916.35, "count": 49, "balance": -212.1, "rate": 0.95})
check = FigureCheckService().check_figures


def test_figures_from_the_data_pass_in_swiss_and_english_writing() -> None:
    answer = (
        "You spent CHF 2'916.35 (2’916.35, 2,916.35, 2 916.35) in 49 purchases,"
        " about 2.9k, at 0.95 %."
    )

    result = check(answer=answer, sources=[RESULT])

    assert result is not None
    assert (result.passed, result.detail) == (True, "7 of 7 found")


def test_a_comma_after_a_figure_ends_the_sentence_part() -> None:
    result = check(answer="An e-bike for CHF 4,500, by April.", sources=["CHF 4500.00"])

    assert result is not None
    assert (result.passed, result.detail) == (True, "1 of 1 found")


def test_a_plain_space_never_joins_two_numbers() -> None:
    result = check(answer="Rate 20 of 24, then 390 more.", sources=["20 24 390"])

    assert result is not None
    assert (result.passed, result.detail) == (True, "3 of 3 found")


def test_an_invented_figure_fails_and_is_named() -> None:
    result = check(answer="CHF 2'916.35 and fees of CHF 39.90, 12 % more.", sources=[RESULT])

    assert result is not None
    assert result.passed is False
    assert result.detail == "1 of 3 found; not found: 39.90, 12 %"


def test_a_debit_counts_without_its_sign() -> None:
    result = check(answer="The Migros purchase was CHF 212.10.", sources=[RESULT])

    assert result is not None
    assert result.passed


@pytest.mark.parametrize(
    "answer",
    [
        "On 31.10.2026 and on 2026-10-31.",
        "In 2026, on 31 October, on 31. Oktober, on October 31 and in October 2026.",
        "1. Netflix and 3 months.",
        "Your rent was paid.",
    ],
)
def test_dates_years_counts_and_plain_text_have_nothing_to_check(answer: str) -> None:
    assert check(answer=answer, sources=[RESULT]) is None


def test_the_customers_own_figures_count() -> None:
    result = check(answer="With CHF 12'000 for Japan, yes.", sources=["Can I afford 12000?"])

    assert result is not None
    assert result.passed


@pytest.mark.parametrize(
    ("answer", "missing"),
    [
        ("Your rent is CHF 2000.", "2000"),
        ("Your rent is 2'050 CHF.", "2'050"),
        ("You paid CHF 5.", "5"),
        ("You may 400 times.", "400"),
        ("CHF 50 may be saved.", "50"),
    ],
)
def test_an_amount_is_checked_even_when_it_looks_like_a_year_or_a_count(
    answer: str, missing: str
) -> None:
    result = check(answer=answer, sources=[RESULT])

    assert result is not None
    assert result.detail == f"0 of 1 found; not found: {missing}"


def test_a_percentage_may_be_a_ratio_in_the_data() -> None:
    result = check(answer="That is 12 % more.", sources=['{"change": 0.12}'])

    assert result is not None
    assert result.passed


def test_a_long_reference_in_a_source_is_skipped_not_a_crash() -> None:
    result = check(
        answer="You paid CHF 39.90.",
        sources=["Referenz 210000000003139471430009017", "0.1234567890123456789012345"],
    )

    assert result is not None
    assert result.detail == "0 of 1 found; not found: 39.90"


def test_a_figure_after_a_narrow_space_is_checked() -> None:
    result = check(answer="IKEA CHF 184.90 and CHF 39.90.", sources=["184.9"])

    assert result is not None
    assert result.detail == "1 of 2 found; not found: 39.90"


check_dates = FigureCheckService().check_dates
SWISSCOM = {"date": "2026-12-14", "amount_chf": -94.0, "counterparty": "Swisscom"}
GLUECKSKETTE = {"date": "2026-12-15", "amount_chf": -50.0, "counterparty": "Glückskette"}


def test_an_amount_beside_another_rows_date_fails() -> None:
    result = check_dates(
        answer=(
            "Due next month:\n- December 15: CHF 94.00, Swisscom\n- 15.12.2026: CHF 50, Glückskette"
        ),
        results=[{"rows": [SWISSCOM, GLUECKSKETTE]}],
        texts=[],
    )

    assert result is not None
    assert (result.name, result.passed) == ("dates_match", False)
    assert result.detail == "1 of 2 matched; not matched: - December 15: CHF 94.00, Swisscom"


def test_an_amount_beside_its_own_rows_date_passes() -> None:
    swisscom = {**SWISSCOM, "date": "2026-12-15"}

    result = check_dates(
        answer="December 15: CHF 94.00, Swisscom", results=[{"rows": [swisscom]}], texts=[]
    )

    assert result is not None
    assert (result.passed, result.detail) == (True, "1 of 1 matched")


@pytest.mark.parametrize(
    "written", ["2026-12-15", "15.12.2026", "15 December", "15. Dezember", "December 15"]
)
def test_each_way_of_writing_a_date_is_read(written: str) -> None:
    rows = [{"rows": [SWISSCOM, {**SWISSCOM, "date": "2026-12-15", "amount_chf": -61.0}]}]

    matched = check_dates(answer=f"{written}: CHF 61.00", results=rows, texts=[])
    other_day = check_dates(answer=f"{written}: CHF 94.00", results=rows, texts=[])

    assert matched is not None and matched.passed
    assert other_day is not None and not other_day.passed


def test_a_written_year_must_match_the_rows_year() -> None:
    result = check_dates(
        answer="15.12.2025: CHF 50.00", results=[{"rows": [GLUECKSKETTE]}], texts=[]
    )

    assert result is not None
    assert not result.passed


def test_a_document_line_with_amount_and_date_counts_as_a_row() -> None:
    result = check_dates(
        answer="Due 30.11.2026: CHF 1'250.00",
        results=[],
        texts=["| Fällig | Betrag |\n| 30.11.2026 | 1'250.00 |"],
    )

    assert result is not None
    assert result.passed


def test_lines_without_a_date_add_no_failure() -> None:
    result = check_dates(
        answer="December 15: CHF 50.00\nIn total CHF 144.00.\nIn December 2026 CHF 7.00.",
        results=[{"rows": [GLUECKSKETTE]}],
        texts=[],
    )

    assert result is not None
    assert (result.passed, result.detail) == (True, "1 of 1 matched")


@pytest.mark.parametrize(
    "answer",
    [
        "You spent CHF 2'916.35 in October 2026.",
        "Your rent was paid on 1 December.",
        "On 14 and 15 December: CHF 94.00 and CHF 50.00.",
    ],
)
def test_an_answer_without_a_line_of_one_amount_and_one_date_gets_no_check(answer: str) -> None:
    assert check_dates(answer=answer, results=[{"rows": [SWISSCOM]}], texts=[]) is None


def test_a_date_written_with_non_breaking_hyphens_is_read() -> None:
    answer = "- **Swisscom**: CHF 94.00 on 2026‑12‑15"

    dates = check_dates(answer=answer, results=[{"rows": [SWISSCOM]}], texts=[])
    figures = check(answer=answer, sources=[json.dumps(SWISSCOM)])

    assert dates is not None and not dates.passed
    assert figures is not None and figures.detail == "1 of 1 found"


TODAY = date(2026, 11, 27)
SEPTEMBER = {"month": "2026-09", "count": 40, "money_out_chf": -3210.4, "money_in_chf": 7800.0}
OCTOBER = {"month": "2026-10", "count": 49, "money_out_chf": -2916.35, "money_in_chf": 7800.0}
BY_MONTH = {
    "count": 89,
    "money_out_chf": -6126.75,
    "money_in_chf": 15600.0,
    "month_most_out": SEPTEMBER,
    "months": [SEPTEMBER, OCTOBER],
}
SEPTEMBER_TO_OCTOBER = ({"date_from": "2026-09-01", "date_to": "2026-10-31"}, BY_MONTH)
# What sum_spending returns: its period is only in the call's arguments.
SPENDING = {"count": 3157, "spent_chf": "372391.31", "groups": [{"spent_chf": "372391.31"}]}
MIGROS = {
    "count": 2,
    "money_out_chf": -430.05,
    "rows": [
        {"date": "2026-10-03", "amount_chf": -413.77},
        {"date": "2026-10-09", "amount_chf": -16.28},
    ],
}


def check_context(answer: str, calls: list[tuple[dict, dict]], today: date = TODAY) -> Check | None:
    return FigureCheckService().check_context(answer=answer, calls=calls, today=today)


@pytest.mark.parametrize(
    "answer",
    [
        "Im Oktober haben Sie CHF 3'210.40 ausgegeben.",
        "Letzten Monat gaben Sie 3’210.40 Franken aus.",
        "You spent CHF 3,210.40 in October.",
        "- **October:** CHF 3210.40",
    ],
)
def test_a_month_rows_figure_given_for_another_month_fails(answer: str) -> None:
    result = check_context(answer=answer, calls=[SEPTEMBER_TO_OCTOBER])

    assert result is not None
    assert (result.name, result.passed) == ("figures_in_context", False)
    assert result.detail is not None and result.detail.startswith(
        "0 of 1 fit; from another period: "
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Im Oktober haben Sie CHF 2'916.35 ausgegeben.",
        "In October 2026 you spent CHF 2,916.35.",
        "Last month you spent CHF 2’916.35.",
        "- September: CHF 3'210.40\n- Oktober: CHF 2'916.35",
    ],
)
def test_a_figure_of_the_named_month_passes(answer: str) -> None:
    result = check_context(answer=answer, calls=[SEPTEMBER_TO_OCTOBER])

    assert result is not None
    assert result.passed, result.detail


@pytest.mark.parametrize(
    "answer",
    [
        "You spent a total of CHF 372,391.31 in the previous month (October 2026).",
        "Your total spending last month amounted to **CHF 372,391.31**.",
        "Im letzten Monat haben Sie CHF 372'391.31 ausgegeben.",
    ],
)
def test_a_total_over_a_longer_period_given_for_one_month_fails(answer: str) -> None:
    no_start = ({"date_to": "2026-10-31", "group_by": "category"}, SPENDING)

    result = check_context(answer=answer, calls=[no_start])

    assert result is not None
    assert result.detail is not None and "from another period: 372" in result.detail


def test_a_total_over_exactly_that_month_passes() -> None:
    october = ({"date_from": "2026-10-01", "date_to": "2026-10-31"}, SPENDING)

    result = check_context(answer="Last month you spent CHF 372,391.31.", calls=[october])

    assert result is not None
    assert result.passed


def test_a_year_written_with_the_month_counts() -> None:
    result = check_context(
        answer="In October 2025 you spent CHF 2,916.35.", calls=[SEPTEMBER_TO_OCTOBER]
    )

    assert result is not None
    assert not result.passed


@pytest.mark.parametrize(
    "answer",
    [
        "You spent CHF 372,391.31.",
        "Last month CHF 372,391.31, this month less.",
        "Seit Januar 2026 zahlen Sie CHF 372'391.31.",
        "From June 2026 to November 2026 you spent CHF 372,391.31.",
        "Im Oktober waren es durchschnittlich CHF 372'391.31.",
        "As of November 26 2026 you spent CHF 372,391.31.",
        "Bis zum heutigen Datum im November 2026 haben Sie CHF 372'391.31 bezahlt.",
        "This year, by October, you spent CHF 372,391.31.",
    ],
)
def test_a_clause_without_one_month_as_its_period_is_not_judged(answer: str) -> None:
    no_start = ({"date_to": "2026-10-31"}, SPENDING)

    assert check_context(answer=answer, calls=[no_start]) is None


def test_a_result_without_a_period_and_a_single_movement_are_not_judged() -> None:
    no_dates = ({"group_by": "category"}, SPENDING)
    september = ({"date_from": "2026-09-01"}, MIGROS)

    assert check_context(answer="Im Oktober CHF 372'391.31.", calls=[no_dates]) is None
    assert check_context(answer="Im Oktober CHF 413.77.", calls=[september]) is None


def test_a_result_that_names_its_own_period_is_judged_by_it() -> None:
    periods = {
        "earlier": {"date_from": "2026-09-01", "date_to": "2026-09-30", "money_out_chf": -3210.4},
        "later": {"date_from": "2026-10-01", "date_to": "2026-10-31", "money_out_chf": -2916.35},
    }

    right = check_context(answer="Im Oktober CHF 2'916.35.", calls=[({}, periods)])
    wrong = check_context(answer="Im Oktober CHF 3'210.40.", calls=[({}, periods)])

    assert right is not None and right.passed
    assert wrong is not None and not wrong.passed


@pytest.mark.parametrize(
    "answer",
    [
        "Sie haben bei der Migros CHF -430.05 ausgegeben.",
        "Migros: -430.05 CHF",
        "Migros: CHF −430.05",
        "**Total spending at Coop**: CHF ‑2,354.67",
    ],
)
def test_a_sum_written_with_a_minus_fails(answer: str) -> None:
    coop = {"money_out_chf": -2354.67, "rows": [{"date": "2026-11-23", "amount_chf": -82.4}]}

    result = check_context(answer=answer, calls=[({}, MIGROS), ({}, coop)])

    assert result is not None
    assert result.passed is False
    assert result.detail is not None and "a sum written with a minus: " in result.detail


@pytest.mark.parametrize(
    ("answer", "result"),
    [
        ("- CHF ‑413.77 at Migros", MIGROS),
        ("Ihr Saldo beträgt CHF -212.10.", {"balance_chf": -212.1}),
        ("Your spending changed by -12 %.", {"money_out_change_percent": -12.0}),
        ("The account fell by CHF -500.00.", {"change_chf": -500.0, "money_out_chf": -500.0}),
    ],
)
def test_a_minus_on_a_movement_a_balance_or_a_change_passes(answer: str, result: dict) -> None:
    checked = check_context(answer=answer, calls=[({}, result)])

    assert checked is not None
    assert checked.passed, checked.detail


@pytest.mark.parametrize(
    "answer",
    [
        "Bei der Migros:\n- CHF 430.05 insgesamt\n- CHF 413.77 auf dem Konto",
        "You spent CHF 430.05 at Migros.",
        "Ausgaben bei Migros:\n- 430.05 CHF",
        "Migros - 430.05 CHF",
        "The total (money_out_chf – 430.05) is CHF 430.05.",
    ],
)
def test_a_list_dash_an_en_dash_or_no_minus_is_no_sign(answer: str) -> None:
    assert check_context(answer=answer, calls=[({}, MIGROS)]) is None


def test_figures_no_result_holds_are_left_to_figures_found() -> None:
    assert check_context(answer="Im Oktober CHF 39.90.", calls=[SEPTEMBER_TO_OCTOBER]) is None
    assert check_context(answer="Im Oktober CHF 2'916.35.", calls=[]) is None
