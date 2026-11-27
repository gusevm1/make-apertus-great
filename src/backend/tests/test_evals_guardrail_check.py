from app.features.guardrails.schemas import GuardrailCategory
from evals.guardrail_check import (
    CATEGORIES,
    FAILED,
    GOLD_PATH,
    GoldItem,
    Verdict,
    load_gold,
    score,
)


def item(label: str, language: str = "en") -> GoldItem:
    return GoldItem(
        id="T1",
        persona="none",
        language=language,
        split="tune",
        label=GuardrailCategory(label),
        text="Hi",
        reason="Test.",
    )


def test_gold_set_covers_every_category_in_both_splits() -> None:
    gold = load_gold(path=GOLD_PATH)
    for split in ("tune", "heldout"):
        labels = {entry.label.value for entry in gold if entry.split == split}
        assert labels == set(CATEGORIES)
    assert len({entry.id for entry in gold}) == len(gold)
    assert all("ß" not in entry.text for entry in gold)


def test_score_counts_precision_recall_and_costly_mistakes() -> None:
    items = [item("ok"), item("ok"), item("forecast"), item("off_topic"), item("ok")]
    verdicts = [
        Verdict(category="ok", language="en"),
        Verdict(category="off_topic", language="en"),
        Verdict(category="ok", language="de"),
        Verdict(category="off_topic", language="en"),
        Verdict(category="tax_advice", language="en"),
    ]

    scores = score(items=items, verdicts=verdicts)

    assert scores["accuracy"] == 2 / 5
    assert scores["false_declines"] == 1
    assert scores["false_pointers"] == 1
    assert scores["missed"] == 1
    assert scores["language_accuracy"] == 4 / 5
    per_category = scores["per_category"]
    assert isinstance(per_category, dict)
    assert per_category["off_topic"] == {"precision": 0.5, "recall": 1.0, "support": 1}
    assert per_category["forecast"]["precision"] is None


def test_failed_check_scores_as_ok_like_the_gate() -> None:
    scores = score(
        items=[item("ok"), item("new_credit")],
        verdicts=[
            Verdict(category=FAILED, language=None),
            Verdict(category=FAILED, language=None),
        ],
    )

    assert scores["accuracy"] == 1 / 2
    assert scores["failed_checks"] == 2
    assert scores["missed"] == 1
