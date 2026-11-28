import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.provenance import Check
from evals import score
from evals.gold import Computed, GoldQuestion, Value, load_gold
from evals.run import ActualCall
from evals.score import Turn, score_turn, select, tool_ok

QUESTION = GoldQuestion.model_validate(
    {
        "id": "l02",
        "customer": "lukas",
        "question": "Wie viel habe ich im Oktober bei der Migros ausgegeben?",
        "category": "period_spending",
        "split": "tune",
        "call_sets": [
            [{"tool": "search_movements", "arguments": {"text": ".*migros.*"}}],
            [
                {"tool": "sum_by_counterparty"},
                {"tool": "search_movements", "arguments": {"kind": ".*spending.*"}},
            ],
        ],
        "not_called": ["list_card_statements"],
        "example": [{"tool": "search_movements"}],
        "figures": [
            {"name": "migros", "source": "ledger"},
            {"name": "on_account", "source": "bookings", "required": False},
        ],
        "decoys": [
            {"name": "with_bill", "failure": "double_counting", "source": "ledger"},
        ],
    }
)
COMPUTED = Computed(
    figures={
        "migros": Value(
            value=Decimal("430.05"),
            count=2,
            ids=["BK-1", "CTX-1"],
            amounts=[Decimal("413.77"), Decimal("16.28")],
        ),
        "on_account": Value(value=Decimal("413.77"), count=1, ids=["BK-1"]),
    },
    decoys={"with_bill": Value(value=Decimal("4805.15"), count=3, ids=[])},
)
RESULT = json.dumps({"money_out_chf": "-430.05", "rows": [{"amount_chf": "-413.77"}]})
SEARCH = ActualCall(tool_name="search_movements", arguments={"text": ["Migros"]}, error=None)


def _turn(answer: str, sources: list[str] | None = None, flagged: str | None = None) -> Turn:
    detail = "1 of 2 found" if flagged is None else f"1 of 2 found; not found: {flagged}"
    check = Check(name="figures_found", passed=flagged is None, detail=detail)
    return Turn(
        answer=answer,
        calls=[SEARCH],
        sources=[RESULT] if sources is None else sources,
        checks=[check],
    )


def _written(folder: Path) -> dict:
    return json.loads(next(folder.glob("*-tune.json")).read_text(encoding="utf-8"))


def _write(path: Path, results: list[dict]) -> None:
    path.write_text(json.dumps({"results": results}), encoding="utf-8")


def _score(turn: Turn) -> score.RunResult:
    return score_turn(question=QUESTION, computed=COMPUTED, turn=turn, run=0)


def test_the_gold_figure_from_a_tool_passes_with_its_parts_allowed() -> None:
    result = _score(
        _turn(answer="Im Oktober CHF 430.05 bei der Migros (Konto 413.77, Karte 16.28).")
    )

    assert result.passed
    assert [verdict.verdict for verdict in result.figures] == ["gold", "gold", "allowed"]
    assert result.failures == []


def test_a_rounded_gold_figure_counts() -> None:
    assert _score(_turn(answer="Rund CHF 430 bei der Migros.")).passed


def test_a_decoy_is_its_failure_and_a_missed_check_is_counted_apart() -> None:
    result = _score(_turn(answer="Sie haben CHF 4'805.15 ausgegeben."))

    assert not result.passed
    assert result.figures[0].verdict == "decoy"
    assert set(result.failures) == {"double_counting", "check_missed_wrong_figure"}


def test_a_right_total_no_tool_returned_was_summed_in_the_answer() -> None:
    sources = [json.dumps({"money_out_chf": "-413.77"}), json.dumps({"money_out_chf": "-16.28"})]

    result = _score(_turn(answer="413.77 + 16.28 = CHF 430.05", sources=sources, flagged="430.05"))

    assert result.figures[-1].verdict == "gold"
    assert "sum_in_answer" in result.failures
    assert "check_missed_wrong_figure" not in result.failures
    assert "check_flagged_right_figure" not in result.failures


def test_a_new_figure_that_adds_up_source_figures_is_a_sum_otherwise_invented() -> None:
    sources = [json.dumps({"a": "-100.50", "b": "-200.25"})]

    summed = _score(_turn(answer="CHF 300.75", sources=sources))
    invented = _score(_turn(answer="CHF 512.40", sources=sources))

    assert summed.figures[0].verdict == "sum_in_answer"
    assert invented.figures[0].verdict == "invented"
    assert "invented_figure" in invented.failures


def test_a_source_figure_instead_of_the_gold_is_wrong_for_the_question() -> None:
    result = _score(_turn(answer="Auf dem Konto waren es CHF 413.77."))

    assert result.missing == ["migros"]
    assert "in_source_but_wrong" in result.failures


def test_no_figure_and_a_flagged_right_figure_are_named() -> None:
    silent = _score(_turn(answer="Dazu sehe ich nichts."))
    flagged = _score(_turn(answer="CHF 430.05", flagged="430.05"))

    assert silent.failures == ["no_figure"]
    assert flagged.passed
    assert flagged.failures == ["check_flagged_right_figure"]


def test_a_minus_before_spending_is_a_wrong_sign() -> None:
    result = _score(_turn(answer="Ausgaben: CHF -430.05"))

    assert "wrong_sign" in result.failures


def test_a_figure_the_context_check_flags_counts_as_flagged() -> None:
    context = Check(
        name="figures_in_context",
        passed=False,
        detail="0 of 1 fit; a sum written with a minus: 430.05",
    )
    turn = _turn(answer="Ausgaben: CHF -430.05").model_copy(
        update={"checks": [*_turn(answer="").checks, context]}
    )

    result = _score(turn)

    assert result.figures[0].flagged
    assert "check_missed_wrong_figure" not in result.failures


def test_a_list_dash_is_no_sign_and_small_whole_numbers_are_no_figures() -> None:
    result = _score(_turn(answer="- CHF 430.05 in 10 Einkäufen am 31. Oktober, Monat 2026-10"))

    assert result.passed
    assert [verdict.text for verdict in result.figures] == ["430.05"]


def test_any_call_set_passes_and_a_forbidden_tool_fails() -> None:
    by_counterparty = ActualCall(tool_name="sum_by_counterparty", arguments={}, error=None)
    spending = ActualCall(
        tool_name="search_movements", arguments={"kind": ["spending"]}, error=None
    )
    statements = ActualCall(
        tool_name="list_card_statements", arguments={"card_id": "CARD-VISA"}, error=None
    )
    failed = ActualCall(tool_name="search_movements", arguments={"text": ["Migros"]}, error="x")

    assert tool_ok(question=QUESTION, calls=[SEARCH])
    assert tool_ok(question=QUESTION, calls=[by_counterparty, spending])
    assert not tool_ok(question=QUESTION, calls=[by_counterparty])
    assert not tool_ok(question=QUESTION, calls=[failed])
    assert not tool_ok(question=QUESTION, calls=[SEARCH, statements])


def test_tune_never_selects_a_held_out_question() -> None:
    questions = load_gold()

    tune = select(questions=questions, split="tune")

    assert tune and all(question.split == "tune" for question in tune)
    assert len(select(questions=questions, split="all")) == len(questions)


async def test_a_tune_run_asks_and_writes_only_tune_questions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, list[str]] = {}

    async def compute_all(questions: list[GoldQuestion], check_paths: bool) -> tuple:
        seen["computed"] = [question.id for question in questions]
        one = Value(value=Decimal(1), count=0, ids=[])
        computed = {
            q.id: Computed(
                figures={figure.name: one for figure in q.figures},
                decoys={decoy.name: one for decoy in q.decoys},
            )
            for q in questions
        }
        return computed, []

    async def ask_all(
        questions: list[GoldQuestion], base_url: str, runs: int, concurrency: int
    ) -> dict:
        seen["asked"] = [question.id for question in questions]
        return {
            (q.id, run): Turn(answer="Dazu sehe ich nichts.")
            for q in questions
            for run in range(runs)
        }

    monkeypatch.setattr(score, "compute_all", compute_all)
    monkeypatch.setattr(score, "ask_all", ask_all)
    monkeypatch.setattr(score, "check_frozen", lambda **_: [])
    monkeypatch.setattr(score, "RESULTS_PATH", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["score", "--base-url", "http://backend", "--split", "tune", "--runs", "2"]
    )

    assert await score.main() == 0

    held_out = {question.id for question in load_gold() if question.split == "held_out"}
    written = _written(folder=tmp_path)
    assert not held_out & set(seen["computed"])
    assert not held_out & set(seen["asked"])
    assert not held_out & {result["question_id"] for result in written["results"]}
    assert list(written["reports"]) == ["tune"]


async def test_rescoring_reads_the_stored_turns_instead_of_asking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    turn = _turn(answer="CHF 430.05")
    earlier = tmp_path / "earlier.json"
    _write(path=earlier, results=[_score(turn).model_dump(mode="json")])

    async def compute_all(questions: list[GoldQuestion], check_paths: bool) -> tuple:
        return {question.id: COMPUTED for question in questions}, []

    async def ask_all(**_: object) -> dict:
        raise AssertionError("a rescore never asks the gateway")

    monkeypatch.setattr(score, "load_gold", lambda: [QUESTION])
    monkeypatch.setattr(score, "compute_all", compute_all)
    monkeypatch.setattr(score, "ask_all", ask_all)
    monkeypatch.setattr(score, "check_frozen", lambda **_: [])
    monkeypatch.setattr(score, "RESULTS_PATH", tmp_path)
    monkeypatch.setattr(sys, "argv", ["score", "--rescore", str(earlier)])

    assert await score.main() == 0
    assert _written(folder=tmp_path)["reports"]["tune"]["passed_runs"] == 1
