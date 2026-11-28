from datetime import date
from decimal import Decimal

from app.features.tiles.meanings import meaning
from app.features.tiles.schemas import SavingsGoalPayload, Source


def payload(withdrawals: int, withdrawn: str) -> SavingsGoalPayload:
    return SavingsGoalPayload(
        figure_chf=Decimal("284.25"),
        source=Source(label="2 transfers", kind="bookings", rows=[], count=2),
        account_name="Sparkonto Notgroschen",
        goal_text="Notgroschen CHF 3'000",
        goal_chf=Decimal("3000"),
        percent=9.5,
        month_change_chf=Decimal("-600"),
        month="2026-11",
        withdrawals_this_year=withdrawals,
        withdrawn_this_year_chf=Decimal(withdrawn),
    )


def test_the_meaning_counts_the_withdrawals_of_the_whole_year() -> None:
    text = meaning(payload=payload(withdrawals=7, withdrawn="1800"), today=date(2026, 11, 27))

    assert "This year it was used 7 times: CHF 1'800.00 taken out in all." in text


def test_an_untouched_fund_says_so() -> None:
    text = meaning(payload=payload(withdrawals=0, withdrawn="0"), today=date(2026, 11, 27))

    assert "Nothing was taken out of it this year." in text
