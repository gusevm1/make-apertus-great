from app.features.tool_calls.totals import total_sentence


def test_a_search_states_its_sum_and_its_period() -> None:
    result = {"count": 11, "money_out_chf": "-2985.4", "money_in_chf": "0", "rows": []}

    sentence = total_sentence(
        result=result, arguments={"date_from": "2026-01-01", "date_to": "2026-11-27"}
    )

    assert sentence == "CHF 2'985.40 went out in 11 bookings between 01.01.2026 and 27.11.2026."


def test_a_search_without_a_period_says_so() -> None:
    result = {"count": 3, "money_out_chf": "-10", "money_in_chf": "5.5", "rows": []}

    sentence = total_sentence(result=result, arguments={})

    assert sentence is not None
    assert "CHF 10.00 went out and CHF 5.50 came in" in sentence
    assert "whole ledger" in sentence


def test_upcoming_payments_and_spending_get_their_sums() -> None:
    upcoming = {"total_chf": 5308.5, "items": [{}, {}]}
    spending = {
        "spent_chf": "289.6",
        "count": 1,
        "groups": [{"group": "health", "spent_chf": "289.6"}],
    }

    assert total_sentence(result=upcoming, arguments={"date_to": "2026-12-23"}) == (
        "CHF 5'308.50 are due in 2 payments until 23.12.2026."
    )
    assert total_sentence(result=spending, arguments={}).startswith("CHF 289.60 were spent")  # type: ignore[union-attr]


def test_a_result_without_a_sum_has_no_sentence() -> None:
    assert total_sentence(result={"items": []}, arguments={}) is None
