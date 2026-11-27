import json

import pytest

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
