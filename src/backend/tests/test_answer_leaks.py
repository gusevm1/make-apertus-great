from app.core.provenance import Check, Provenance
from app.features.conversations.prompts import incomplete_answer
from app.features.conversations.service import _complete
from app.features.figure_checks.service import FigureCheckService, _prompt_sentences

CHECKS = FigureCheckService()


def provenance(checks: list[Check]) -> Provenance:
    return Provenance(model="apertus", latency_ms=1, checks=checks)


def test_an_amount_left_open_fails_the_check() -> None:
    check = CHECKS.check_complete(answer="Average monthly cost: CHF ?. Garage CHF ?")

    assert check is not None
    assert check.name == "answer_complete"
    assert check.passed is False
    assert check.detail == "an amount left open (CHF ?)"


def test_a_currency_the_corrector_left_without_its_amount_fails_the_check() -> None:
    check = CHECKS.check_complete(answer="After these bills, CHF will remain until the salary.")

    assert check is not None
    assert check.detail == "an amount left open (CHF ?)"


def test_a_currency_named_as_the_unit_passes() -> None:
    answer = "All amounts are in CHF per month. Of CHF 124.96, CHF 4.63 a day is left."

    assert CHECKS.check_complete(answer=answer) is None


def test_a_sentence_of_the_instructions_fails_the_check() -> None:
    leaked = next(iter(_prompt_sentences()))

    check = CHECKS.check_complete(answer=f"There is no such chart.\n\n{leaked.capitalize()}")

    assert check is not None
    assert check.detail == "a sentence of the instructions"


def test_a_normal_answer_has_no_check() -> None:
    answer = "You spent CHF 204.00 on restaurants from 01.11. to 27.11. Is that what you expected?"

    assert CHECKS.check_complete(answer=answer) is None


def test_a_held_answer_that_failed_is_replaced_and_keeps_its_checks() -> None:
    failed = Check(name="answer_complete", passed=False, detail="an amount left open (CHF ?)")

    content, kept = _complete(content="CHF ?", provenance=provenance([failed]), can_replace=True)

    assert content == incomplete_answer()
    assert kept.checks == [failed]


def test_a_streamed_answer_that_failed_stays_but_is_flagged() -> None:
    failed = Check(name="answer_complete", passed=False, detail="an amount left open (CHF ?)")

    content, kept = _complete(content="CHF ?", provenance=provenance([failed]), can_replace=False)

    assert content == "CHF ?"
    assert kept.checks == [failed]
