from datetime import date
from decimal import Decimal

import pytest

from app.features.tiles.meanings import meaning
from app.features.tiles.schemas import PaydayAlternative, PaydayBalancePayload, Source

TODAY = date(2026, 11, 27)


def payday(
    left: str, per_day: str, alternative: PaydayAlternative | None = None
) -> PaydayBalancePayload:
    return PaydayBalancePayload(
        figure_chf=Decimal(left),
        source=Source(label="Privatkonto", kind="payments", rows=[], count=0),
        account_name="Privatkonto",
        payday=date(2026, 12, 24),
        day_before=date(2026, 12, 23),
        days=27,
        per_day_chf=Decimal(per_day),
        today=TODAY,
        today_balance_chf=Decimal("3075.16"),
        points=[],
        upcoming_count=8,
        alternative=alternative,
    )


@pytest.mark.parametrize(
    ("left", "per_day", "verdict"),
    [
        ("124.96", "4.63", "Yes, but only just. The money lasts:"),
        ("1174.96", "43.52", "Yes. The money lasts:"),
        ("5400.00", "200.00", "Yes, comfortably. The money lasts:"),
        ("-80.00", "-2.96", "No. The money does not last:"),
    ],
)
def test_the_payday_verdict_comes_from_the_figures(left: str, per_day: str, verdict: str) -> None:
    assert meaning(payload=payday(left=left, per_day=per_day), today=TODAY).startswith(verdict)


def test_the_payday_meaning_names_the_missing_income_in_swiss_figures() -> None:
    alternative = PaydayAlternative(
        counterparty="Patrick Rüegg",
        label="the child support",
        amount_chf=Decimal("1050.00"),
        left_chf=Decimal("1174.96"),
        per_day_chf=Decimal("43.52"),
    )

    text = meaning(
        payload=payday(left="124.96", per_day="4.63", alternative=alternative), today=TODAY
    )

    assert "CHF 124.96 are left on 23.12. That is CHF 4.63 a day for 27 days." in text
    assert "The second case: the child support from Patrick Rüegg (CHF 1'050.00)" in text
    assert text.endswith("if it arrives, CHF 1'174.96 are left on 23.12.")
