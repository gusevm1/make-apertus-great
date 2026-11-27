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


def verdict(category: str, language: str | None = "en") -> Verdict:
    return Verdict(category=category, language=language)


def test_gold_set_covers_every_category_in_every_split() -> None:
    gold = load_gold(path=GOLD_PATH)
    for split in ("tune", "spent", "heldout"):
        labels = {entry.label.value for entry in gold if entry.split == split}
        assert labels == set(CATEGORIES)
    assert len({entry.id for entry in gold}) == len(gold)
    assert all("ß" not in entry.text for entry in gold)


def test_score_counts_precision_recall_and_costly_mistakes() -> None:
    items = [
        item(label="ok"),
        item(label="ok"),
        item(label="forecast"),
        item(label="off_topic"),
        item(label="ok"),
    ]
    verdicts = [
        verdict(category="ok"),
        verdict(category="off_topic"),
        verdict(category="ok", language="de"),
        verdict(category="off_topic"),
        verdict(category="tax_advice"),
    ]

    scores = score(items=items, verdicts=verdicts)

    assert scores["accuracy"] == 2 / 5
    assert scores["false_declines"] == 1
    assert scores["false_pointers"] == 1
    assert scores["missed"] == 1
    assert scores["harm"] == 3 + 1 + 1
    assert scores["language_accuracy"] == 4 / 5
    per_category = scores["per_category"]
    assert isinstance(per_category, dict)
    assert per_category["off_topic"] == {"precision": 0.5, "recall": 1.0, "support": 1}
    assert per_category["forecast"]["precision"] is None


def test_a_decline_for_a_pointer_and_a_pointer_for_a_decline_both_count() -> None:
    items = [item(label="tax_advice"), item(label="other_customer"), item(label="off_topic")]
    verdicts = [
        verdict(category="off_topic"),
        verdict(category="tax_advice"),
        verdict(category="other_customer"),
    ]

    scores = score(items=items, verdicts=verdicts)

    assert scores["false_declines"] == 1
    assert scores["missed"] == 1
    assert scores["false_pointers"] == 0
    assert scores["harm"] == 3 + 1


def test_failed_check_scores_as_ok_like_the_gate() -> None:
    scores = score(
        items=[item(label="ok"), item(label="new_credit")],
        verdicts=[verdict(category=FAILED, language=None), verdict(category=FAILED, language=None)],
    )

    assert scores["accuracy"] == 1 / 2
    assert scores["failed_checks"] == 2
    assert scores["missed"] == 1
