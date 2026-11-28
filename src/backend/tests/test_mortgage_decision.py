from datetime import date
from decimal import Decimal

import pytest

from app.features.tiles.meanings import meaning
from app.features.tiles.schemas import MortgagePayload, Source, Tranche
from app.features.tiles.service import TileError, _account, _decision

REMARKS = (
    "Läuft am 31.03.2027 aus. Verlängerungsofferte vom 05.11.2026, Entscheid bis 15.12.2026. "
    "Ohne Entscheid automatische Umwandlung in SARON-Hypothek."
)


def test_the_decision_date_and_its_consequence_come_from_the_remarks() -> None:
    assert _decision(remarks=REMARKS) == {
        "decide_by": date(2026, 12, 15),
        "without_decision": "Ohne Entscheid automatische Umwandlung in SARON-Hypothek.",
    }
    assert _decision(remarks="2019–2022 Festhypothek 3 Jahre, seit 01.04.2022 SARON.") == {}
    assert _decision(remarks=None) == {}


def test_the_mortgage_meaning_names_the_decision_date() -> None:
    tranche = Tranche(
        loan_id="LOAN-02",
        product="Festhypothek 8 Jahre",
        balance_chf=Decimal("350000"),
        interest_rate=0.95,
        maturity_date=date(2027, 3, 31),
        next_interest_date=None,
        **_decision(remarks=REMARKS),
    )
    payload = MortgagePayload(
        figure_chf=Decimal("350000"),
        source=Source(label="1 tranche", kind="loans", rows=[], count=1),
        annual_interest_chf=Decimal("3325"),
        tranches=[tranche],
        next_maturity=tranche,
        next_decision=tranche,
    )

    text = meaning(payload=payload, today=date(2026, 11, 27))

    assert "needs a decision on the Festhypothek 8 Jahre by 15.12.2026" in text
    assert "Ohne Entscheid automatische Umwandlung in SARON-Hypothek." in text


def test_a_tranche_asked_as_an_account_points_to_the_mortgage_tile() -> None:
    accounts = [{"account_id": "ACC-PRIV", "name": "Privatkonto"}]

    with pytest.raises(TileError, match="the mortgage template lists each one"):
        _account(accounts=accounts, account_id="TRANCHE1")
    with pytest.raises(TileError) as error:
        _account(accounts=accounts, account_id="ACC-XYZ")
    assert "mortgage" not in str(error.value)
