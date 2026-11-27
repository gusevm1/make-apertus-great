from collections import Counter
from datetime import date
from decimal import Decimal

from evals import reference
from evals.gold import (
    Bank,
    BankReader,
    GoldFigure,
    Kind,
    Row,
    SecondPath,
    Spec,
    Term,
    Value,
    booking_kind,
    evaluate,
    evaluate_term,
    freeze,
    load_frozen,
    load_gold,
    unreachable,
)

OWN_IBAN = "CH0000000000000000001"


def _row(
    row_id: str,
    amount: str,
    text: str,
    kind: Kind = "spending",
    day: date = date(2026, 10, 15),
    type: str | None = None,
    card: str | None = None,
) -> Row:
    return Row(
        id=row_id, date=day, amount=Decimal(amount), text=text, kind=kind, type=type, card=card
    )


BOOKINGS = [
    _row("BK-1", "-413.77", text="Kartenzahlung MIGROS M ZUERICH Migros", type="debit_card"),
    _row("BK-2", "-600.00", text="Dauerauftrag Säule 3a", kind="own_transfer"),
    _row("BK-3", "-4375.10", text="Visa Gold Abrechnung", kind="card_settlement"),
    _row("BK-4", "8742.35", text="Lohn", kind="credit", type="salary"),
    _row("BK-5", "-12.00", text="Migros", day=date(2026, 11, 2)),
]
CARD = [
    _row("CTX-1", "-16.28", text="MIGROS TAKE AWAY Migros Take Away", card="CARD-VISA"),
    _row("CTX-2", "59.00", text="DIGITEC Digitec", kind="credit", card="CARD-VISA"),
]
BANK = Bank(
    ledger=BOOKINGS + CARD, bookings=BOOKINGS, cards=CARD, accounts=[], loans=[], upcoming=[]
)
OCTOBER_FROM, OCTOBER_TO = date(2026, 10, 1), date(2026, 10, 31)


def test_ledger_spending_leaves_out_own_transfers_bills_and_other_months() -> None:
    value = evaluate(
        spec=Spec(source="ledger", kind=["spending"], date_from=OCTOBER_FROM, date_to=OCTOBER_TO),
        rows=BANK.ledger,
    )

    assert value.value == Decimal("430.05")
    assert value.ids == ["BK-1", "CTX-1"]
    assert value.amounts == [Decimal("413.77"), Decimal("16.28")]


def test_words_match_at_the_start_of_a_word_on_account_and_card() -> None:
    value = evaluate(
        spec=Spec(source="ledger", text=["migros"], date_from=OCTOBER_FROM, date_to=OCTOBER_TO),
        rows=BANK.ledger,
    )

    assert value.value == Decimal("430.05")


def test_a_card_refund_is_money_in_and_a_minus_term_nets_it() -> None:
    refund = evaluate(
        spec=Spec(
            source="ledger",
            card="CARD-VISA",
            measure="in",
            date_from=OCTOBER_FROM,
            date_to=OCTOBER_TO,
        ),
        rows=BANK.ledger,
    )
    net = evaluate_term(
        term=Term(
            source="ledger",
            kind=["spending"],
            minus=[
                Spec(
                    source="ledger",
                    card="CARD-VISA",
                    measure="in",
                    date_from=OCTOBER_FROM,
                    date_to=OCTOBER_TO,
                )
            ],
            date_from=OCTOBER_FROM,
            date_to=OCTOBER_TO,
        ),
        bank=BANK,
    )

    assert refund.value == Decimal("59.00")
    assert net.value == Decimal("371.05")


def test_bookings_count_the_card_bill_the_ledger_leaves_out() -> None:
    bill = evaluate(
        spec=Spec(source="bookings", type=[], date_from=OCTOBER_FROM, date_to=OCTOBER_TO),
        rows=BANK.bookings,
    )

    assert bill.value == Decimal("5388.87")


def test_own_ibans_and_bills_get_their_own_kind() -> None:
    def kind(transaction_type: str, amount: float, iban: str | None = None) -> str:
        booking = {"transaction_type": transaction_type, "amount": amount}
        return booking_kind(booking=booking | {"counterparty_iban": iban}, own_ibans={OWN_IBAN})

    assert kind("card_settlement", -100) == "card_settlement"
    assert kind("securities_buy", -600) == "own_transfer"
    assert kind("standing_order", -500, iban="CH00 0000 0000 0000 0000 1") == "own_transfer"
    assert kind("incoming_transfer", 88.7) == "credit"
    assert kind("debit_card", -12) == "spending"


def test_a_frozen_figure_is_kept_and_never_changed() -> None:
    frozen: dict = {}
    first = Value(value=Decimal("430.05"), count=10, ids=[])

    assert freeze(frozen=frozen, question_id="l02", name="migros", value=first) is None
    assert freeze(frozen=frozen, question_id="l02", name="migros", value=first) is None
    changed = Value(value=Decimal("413.77"), count=9, ids=[])
    problem = freeze(frozen=frozen, question_id="l02", name="migros", value=changed)

    assert problem is not None and "never refreeze" in problem
    assert frozen["l02"]["migros"] == {"value": "430.05", "count": 10}


def test_a_required_group_missing_from_every_tool_result_is_unreachable() -> None:
    figures = [
        GoldFigure(name="gross", group="spent", source="ledger"),
        GoldFigure(name="net", group="spent", source="ledger"),
        GoldFigure(name="refund", source="ledger"),
        GoldFigure(name="part", source="ledger", required=False),
    ]
    values = {
        "gross": Value(value=Decimal("2975.35"), count=1, ids=[]),
        "net": Value(value=Decimal("2916.35"), count=1, ids=[]),
        "refund": Value(value=Decimal("59.00"), count=1, ids=[]),
        "part": Value(value=Decimal("16.28"), count=1, ids=[]),
    }
    results = ['{"money_out_chf": "-2975.35", "count": 48}']

    assert unreachable(figures=figures, values=values, results=results) == ["refund"]


def test_the_reference_path_reads_the_seed_csvs_with_its_own_rules() -> None:
    second = SecondPath(
        reader=BankReader(client=None, base_url="", token=""),  # type: ignore[arg-type]
        folder=reference.DATA_PATH / reference.CUSTOMERS["lukas"],
    )

    value = second.reference(
        spec=Spec(source="ledger", text=["Migros"], date_from=OCTOBER_FROM, date_to=OCTOBER_TO)
    )

    assert value.value == Decimal("430.05")
    assert "CTX-01403" in value.ids


def test_the_split_is_fixed_by_template_category_and_customer() -> None:
    questions = load_gold()
    held_out = [question for question in questions if question.split == "held_out"]
    sides: dict[str, set[str]] = {}
    for question in questions:
        if question.template is not None:
            sides.setdefault(question.template, set()).add(question.split)

    assert 0.25 <= len(held_out) / len(questions) <= 0.4
    assert all(len(split) == 1 for split in sides.values())
    assert {question.customer for question in held_out} == {"lukas", "jana", "daniela", "marco"}
    by_category = Counter(question.category for question in questions)
    held_by_category = Counter(question.category for question in held_out)
    assert all(held_by_category[category] >= 1 for category in by_category)
    assert all(held_by_category[category] < count for category, count in by_category.items())


def test_every_gold_figure_is_frozen_and_ids_are_unique() -> None:
    questions = load_gold()
    frozen = load_frozen()

    assert len({question.id for question in questions}) == len(questions)
    for question in questions:
        names = {figure.name for figure in question.figures}
        assert names == set(frozen.get(question.id, {})), question.id
        assert len(names) == len(question.figures), question.id
