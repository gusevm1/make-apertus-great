from typing import Any

from evals.categorisation import load_gold, score, split_of


def _gold(uid: str, category: str, hard: list[str] | None = None) -> dict[str, Any]:
    return {
        "uid": uid,
        "persona": "lukas",
        "category": category,
        "hard": hard or [],
        "seen": {"text": uid, "amount_chf": "10.0"},
    }


def _tag(
    category: str,
    certainty: str | None = "high",
    set_by: str = "model",
    usual: str | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "category_certainty": certainty,
        "category_set_by": set_by,
        "category_confirmed": set_by == "customer",
        "payee_usual_category": usual or category,
    }


def test_the_split_is_by_payee_and_stable() -> None:
    assert split_of(persona="lukas", payee="migros") == split_of(persona="lukas", payee="migros")
    splits = {split_of(persona="lukas", payee=f"payee {number}") for number in range(40)}
    assert splits == {"tune", "heldout"}


def test_every_gold_row_carries_its_split_and_a_valid_category() -> None:
    gold = load_gold()

    assert len({row["uid"] for row in gold}) == len(gold)
    assert all(row["split"] == split_of(persona=row["persona"], payee=row["payee"]) for row in gold)
    held_out = sum(row["split"] == "heldout" for row in gold) / len(gold)
    assert 0.15 < held_out < 0.35


def test_score_counts_customer_rows_apart_and_a_missing_row_as_wrong() -> None:
    gold = [
        _gold("a", "groceries"),
        _gold("b", "shopping"),
        _gold("c", "restaurants", hard=["multi_payee"]),
        _gold("d", "transport"),
    ]
    tags = {
        "a": _tag("groceries"),
        "b": _tag("groceries", certainty="high"),
        "c": _tag("restaurants", set_by="customer"),
    }

    result = score(gold=gold, tags=tags)

    assert result["scored"] == 3
    assert result["accuracy"] == 1 / 3
    assert result["missing"] == 1
    assert result["fixed_by_rule_or_customer"] == 1
    assert result["wrong_and_high"] == 1
    assert result["confusions"] == [("shopping -> groceries", 1)]


def test_review_catches_a_wrong_row_that_is_unsure_or_unlike_its_payee() -> None:
    gold = [_gold("a", "shopping"), _gold("b", "shopping"), _gold("c", "shopping")]
    tags = {
        "a": _tag("groceries", certainty="low"),
        "b": _tag("groceries", usual="shopping"),
        "c": _tag("groceries"),
    }

    result = score(gold=gold, tags=tags)

    assert result["review_catches_wrong"] == 2 / 3
    assert result["calibration"] == {
        "low": {"right": 0, "wrong": 1},
        "high": {"right": 0, "wrong": 2},
    }
