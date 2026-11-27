"""Scores Apertus against the gold figure questions through a running backend, per split."""

import argparse
import asyncio
import itertools
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from app.core.provenance import Check
from app.features.figure_checks.service import Figure, _figures, _found, _is_count_or_year
from evals.gold import (
    Computed,
    Failure,
    GoldQuestion,
    check_frozen,
    compute_all,
    load_frozen,
    load_gold,
)
from evals.run import TURN_TIMEOUT_SECONDS, ActualCall, EvalSettings, log_in, matches

RESULTS_PATH = Path(__file__).with_name("logs") / "gold"
# The final checks whose flags count, not the draft's before a correction.
CHECK_NAMES = ("figures_found", "figures_in_context")
# Sums of more answer figures than this are not tried, since the subsets grow as 2^n.
MAX_ADDENDS = 12
MIN_ADDEND = Decimal(10)
SMALL_WHOLE = 100
# Constants an answer may name without a tool: the card's fx fee.
CONSTANTS = [Decimal("1.75")]
ANSWER_FAILURES: set[Failure] = {
    "invented_figure",
    "sum_in_answer",
    "double_counting",
    "wrong_sign",
    "wrong_currency",
    "wrong_date_range",
    "in_source_but_wrong",
    "no_figure",
}
Verdict = Literal["gold", "allowed", "decoy", "sum_in_answer", "invented", "in_source"]


class Turn(BaseModel):
    answer: str = ""
    calls: list[ActualCall] = []
    # Every tool result and the customer's profile, the sources the app checks figures against.
    sources: list[str] = []
    checks: list[Check] = []
    error: str | None = None


class FigureVerdict(BaseModel):
    text: str
    verdict: Verdict
    failure: Failure | None = None
    # What it matched: a gold figure, a decoy, or the figures it is a sum of.
    matched: str | None = None
    # A figure in no source is one the figure check can catch.
    in_source: bool = True
    flagged: bool = False


class RunResult(BaseModel):
    question_id: str
    split: str
    category: str
    customer: str
    run: int
    answer: str
    calls: list[str]
    tool_ok: bool
    figures: list[FigureVerdict]
    missing: list[str]
    failures: list[Failure]
    checks: list[Check]
    error: str | None
    # The turn as asked, so a later scorer can score it again without the gateway.
    turn: Turn

    @property
    def passed(self) -> bool:
        return self.error is None and self.tool_ok and not set(self.failures) & ANSWER_FAILURES


def tool_ok(question: GoldQuestion, calls: list[ActualCall]) -> bool:
    if any(call.tool_name in question.not_called for call in calls):
        return False
    return any(
        all(
            any(matches(expected=expected, actual=call) for call in calls) for expected in calls_set
        )
        for calls_set in question.call_sets
    )


def found_in(figure: Figure, values: list[Decimal] | set[Decimal]) -> bool:
    return _found(figure=figure, values=set(values))


def flagged_texts(checks: list[Check]) -> set[str]:
    """The figures the checks name after their counts, as in "2 of 3 found; not found: a, b"."""
    texts: set[str] = set()
    for check in checks:
        if check.passed or check.detail is None:
            continue
        for part in check.detail.split("; ")[1:]:
            texts |= set(part.split(": ", 1)[-1].split(", "))
    return texts


def has_minus(answer: str, text: str) -> bool:
    # Right before the number or after the currency, so a list's "- CHF 430.05" is no sign.
    number = re.escape(text)
    return re.search(rf"[-−‑]{number}|CHF\s?[-−‑]\s?{number}", answer) is not None


def sum_of(figure: Figure, values: list[Decimal], largest_subset: int) -> list[Decimal] | None:
    """Values whose sum, or the difference of two, is the figure."""
    for size in range(2, min(len(values), largest_subset) + 1):
        for addends in itertools.combinations(values, size):
            if found_in(figure=figure, values=[sum(addends, Decimal(0))]):
                return list(addends)
    for first, second in itertools.combinations(values, 2):
        if found_in(figure=figure, values=[abs(first - second)]):
            return [first, second]
    return None


def is_small_whole(figure: Figure) -> bool:
    """A bare whole number below 100, such as a day, a month or a count of bookings."""
    is_bare = not (figure.is_amount or figure.is_percent or figure.is_kilo)
    return is_bare and figure.decimals == 0 and figure.value < SMALL_WHOLE


def classify(
    question: GoldQuestion, computed: Computed, answer: str, sources: list[str]
) -> tuple[list[FigureVerdict], list[str]]:
    """Each figure of the answer with its verdict, and the required gold groups it lacks."""
    figures = [
        figure
        for figure in _figures(text=answer)
        if not _is_count_or_year(figure) and not is_small_whole(figure=figure)
    ]
    source_values = {figure.value for source in sources for figure in _figures(text=source)}
    # Counts, months and days are no amounts to add.
    money = sorted(value for value in source_values if value >= MIN_ADDEND)
    gold = {figure.name: computed.figures[figure.name].value for figure in question.figures}
    allowed = [
        amount
        for figure in question.figures
        for amount in [computed.figures[figure.name].count, *computed.figures[figure.name].amounts]
    ]
    allowed = [Decimal(value) for value in allowed] + CONSTANTS
    verdicts: list[FigureVerdict] = []
    for figure in figures:
        verdicts.append(
            verdict_for(
                figure=figure,
                gold=gold,
                allowed=allowed,
                decoys={name: value.value for name, value in computed.decoys.items()},
                failures={decoy.name: decoy.failure for decoy in question.decoys},
                source_values=source_values,
                money=money,
                others=[other.value for other in figures if other is not figure],
                answer=answer,
            )
        )
    matched = {verdict.matched for verdict in verdicts if verdict.verdict == "gold"}
    groups: dict[str, list[str]] = {}
    for figure in question.figures:
        if figure.required:
            groups.setdefault(figure.group_name, []).append(figure.name)
    missing = [group for group, names in groups.items() if not matched & set(names)]
    return verdicts, missing


def verdict_for(
    figure: Figure,
    gold: dict[str, Decimal],
    allowed: list[Decimal],
    decoys: dict[str, Decimal],
    failures: dict[str, Failure],
    source_values: set[Decimal],
    money: list[Decimal],
    others: list[Decimal],
    answer: str,
) -> FigureVerdict:
    in_source = found_in(figure=figure, values=source_values)
    verdict = _verdict(
        figure=figure,
        gold=gold,
        allowed=allowed,
        decoys=decoys,
        failures=failures,
        in_source=in_source,
        money=money,
        others=others,
        answer=answer,
    )
    verdict.in_source = in_source
    return verdict


def _verdict(
    figure: Figure,
    gold: dict[str, Decimal],
    allowed: list[Decimal],
    decoys: dict[str, Decimal],
    failures: dict[str, Failure],
    in_source: bool,
    money: list[Decimal],
    others: list[Decimal],
    answer: str,
) -> FigureVerdict:
    for name, value in gold.items():
        if not found_in(figure=figure, values=[value]):
            continue
        if has_minus(answer=answer, text=figure.text):
            return FigureVerdict(
                text=figure.text, verdict="gold", failure="wrong_sign", matched=name
            )
        # A right value no tool returned was added up in the answer step.
        failure = None if in_source else "sum_in_answer"
        return FigureVerdict(text=figure.text, verdict="gold", failure=failure, matched=name)
    if found_in(figure=figure, values=allowed):
        return FigureVerdict(text=figure.text, verdict="allowed")
    for name, value in decoys.items():
        if value != 0 and found_in(figure=figure, values=[value]):
            return FigureVerdict(
                text=figure.text, verdict="decoy", failure=failures[name], matched=name
            )
    if in_source:
        return FigureVerdict(text=figure.text, verdict="in_source")
    addends = sum_of(figure=figure, values=others[:MAX_ADDENDS], largest_subset=MAX_ADDENDS)
    if addends is None:
        addends = sum_of(figure=figure, values=money, largest_subset=2)
    if addends is not None:
        return FigureVerdict(
            text=figure.text,
            verdict="sum_in_answer",
            failure="sum_in_answer",
            matched=" + ".join(str(value) for value in addends),
        )
    return FigureVerdict(text=figure.text, verdict="invented", failure="invented_figure")


def is_wrong(verdict: FigureVerdict, missing: list[str]) -> bool:
    """A failure itself, or a source figure given where the gold figure is missing."""
    return verdict.failure is not None or (bool(missing) and verdict.verdict == "in_source")


def score_turn(question: GoldQuestion, computed: Computed, turn: Turn, run: int) -> RunResult:
    checks = [check for check in turn.checks if check.name in CHECK_NAMES]
    sources = [*turn.sources, question.question]
    verdicts, missing = classify(
        question=question, computed=computed, answer=turn.answer, sources=sources
    )
    flagged = flagged_texts(checks=checks)
    failures: list[Failure] = []
    for verdict in verdicts:
        verdict.flagged = verdict.text in flagged
        if verdict.failure is not None:
            failures.append(verdict.failure)
    if missing and not failures:
        failures.append("in_source_but_wrong" if verdicts else "no_figure")
    for verdict in verdicts:
        wrong = is_wrong(verdict=verdict, missing=missing)
        if wrong and not verdict.flagged:
            failures.append("check_missed_wrong_figure")
        if not wrong and verdict.flagged:
            failures.append("check_flagged_right_figure")
    return RunResult(
        question_id=question.id,
        split=question.split,
        category=question.category,
        customer=question.customer,
        run=run,
        answer=turn.answer,
        calls=[f"{call.tool_name}({call.arguments})" for call in turn.calls],
        tool_ok=tool_ok(question=question, calls=turn.calls),
        figures=verdicts,
        missing=missing,
        failures=failures,
        checks=checks,
        error=turn.error,
        turn=turn,
    )


async def ask(client: httpx.AsyncClient, question: str, profile: str) -> Turn:
    """One turn in a new conversation, with the reply, its checks and every tool result."""
    conversation = await client.post("/api/conversations", json={"title": "gold eval"})
    if conversation.status_code != 201:
        return Turn(error=f"no conversation: {conversation.status_code}")
    path = f"/api/conversations/{conversation.json()['id']}"
    try:
        reply = await client.post(
            f"{path}/messages", json={"content": question, "quotes": [], "document_ids": []}
        )
        if reply.status_code != 201:
            return Turn(error=f"turn failed: {reply.status_code} {reply.text[:200]}")
        calls = (await client.get(f"{path}/tool-calls")).json()
        provenance = reply.json()["provenance"] or {}
        answer = reply.json()["content"]
        results = [
            json.dumps(call["result"], ensure_ascii=False)
            for call in calls
            if call["result"] is not None
        ]
        return Turn(
            answer=answer,
            calls=[ActualCall.model_validate(call) for call in calls],
            sources=[*results, profile],
            error="empty answer" if answer.strip() == "" else None,
            checks=[Check.model_validate(check) for check in provenance.get("checks", [])],
        )
    finally:
        await client.delete(path)


async def ask_all(
    questions: list[GoldQuestion], base_url: str, runs: int, concurrency: int
) -> dict[tuple[str, int], Turn]:
    settings = EvalSettings()
    limit = asyncio.Semaphore(concurrency)
    turns: dict[tuple[str, int], Turn] = {}
    async with httpx.AsyncClient(timeout=TURN_TIMEOUT_SECONDS) as bank:
        tokens = {
            customer: await log_in(bank=bank, customer=customer, settings=settings)
            for customer in sorted({question.customer for question in questions})
        }
        profiles = {
            customer: (
                await bank.get(
                    f"{settings.banking_api_url}/customer",
                    headers={"Authorization": f"Bearer {token}"},
                )
            ).text
            for customer, token in tokens.items()
        }

    async def one(question: GoldQuestion, run: int) -> None:
        async with (
            limit,
            httpx.AsyncClient(
                base_url=base_url,
                timeout=TURN_TIMEOUT_SECONDS,
                headers={"Authorization": f"Bearer {tokens[question.customer]}"},
            ) as client,
        ):
            try:
                turn = await ask(
                    client=client, question=question.question, profile=profiles[question.customer]
                )
            # One broken turn must not lose the turns already paid for on the gateway.
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                turn = Turn(error=f"request failed: {error!r}")
            turns[(question.id, run)] = turn
            print(f"  asked {question.id} run {run + 1}", flush=True)  # noqa: T201

    await asyncio.gather(
        *(one(question=question, run=run) for run in range(runs) for question in questions)
    )
    return turns


def summary(results: list[RunResult], runs: int) -> dict[str, Any]:
    by_question: dict[str, list[RunResult]] = {}
    for result in results:
        by_question.setdefault(result.question_id, []).append(result)
    failures = Counter(failure for result in results for failure in set(result.failures))
    return {
        "runs": runs,
        "questions": len(by_question),
        "passed_runs": sum(result.passed for result in results),
        "all_runs": len(results),
        "tool_ok_runs": sum(result.tool_ok for result in results),
        "passed_per_question": {
            question_id: sum(result.passed for result in question_results)
            for question_id, question_results in by_question.items()
        },
        # Runs with at least one figure of that failure type.
        "failures": dict(failures.most_common()),
        "check_missed_wrong_figures": sum(
            result.failures.count("check_missed_wrong_figure") for result in results
        ),
        # The part of those the check could have caught: figures in no tool result.
        "check_missed_not_in_any_source": sum(
            is_wrong(verdict=verdict, missing=result.missing)
            and not verdict.flagged
            and not verdict.in_source
            for result in results
            for verdict in result.figures
        ),
        "check_flagged_right_figures": sum(
            result.failures.count("check_flagged_right_figure") for result in results
        ),
    }


def format_summary(split: str, report: dict[str, Any], questions: list[GoldQuestion]) -> str:
    by_id = {question.id: question for question in questions}
    lines = [f"## {split}: {report['passed_runs']} of {report['all_runs']} runs passed"]
    lines.append(f"tool choice right in {report['tool_ok_runs']} of {report['all_runs']} runs")
    for question_id, passed in report["passed_per_question"].items():
        question = by_id[question_id]
        lines.append(
            f"{passed}/{report['runs']}  {question_id} {question.category:15}"
            f" {question.question[:70]}"
        )
    lines.append("failures (runs): " + ", ".join(f"{k} {v}" for k, v in report["failures"].items()))
    lines.append(
        f"figure check: missed {report['check_missed_wrong_figures']} wrong figures"
        f" ({report['check_missed_not_in_any_source']} in no source),"
        f" flagged {report['check_flagged_right_figures']} right ones"
    )
    return "\n".join(lines)


def commit() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    )
    return head.stdout.strip()


def write_results(split: str, reports: dict[str, Any], results: list[RunResult]) -> Path:
    """One file per run, so a later prompt card can diff its results with this one."""
    RESULTS_PATH.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_PATH / f"{stamp}-{split}.json"
    content = {
        "commit": commit(),
        "split": split,
        "reports": reports,
        "results": [
            result.model_dump(mode="json") | {"passed": result.passed} for result in results
        ],
    }
    path.write_text(json.dumps(content, indent=1, ensure_ascii=False))
    return path


def earlier_turns(path: Path, questions: list[GoldQuestion]) -> dict[tuple[str, int], Turn]:
    """The turns of an earlier results file, only those of the selected questions."""
    asked = {question.id for question in questions}
    results = json.loads(path.read_text())["results"]
    return {
        (result["question_id"], result["run"]): Turn.model_validate(result["turn"])
        for result in results
        if result["question_id"] in asked
    }


def select(questions: list[GoldQuestion], split: str) -> list[GoldQuestion]:
    """The questions of one split; held-out ones are never asked for `tune`."""
    if split == "all":
        return questions
    return [question for question in questions if question.split == split]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=EvalSettings().evals_base_url)
    parser.add_argument("--split", choices=["tune", "held_out", "all"], default="tune")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--only", nargs="*", default=None, help="question ids of the split")
    parser.add_argument(
        "--rescore",
        type=Path,
        default=None,
        help="score the turns of an earlier results file again",
    )
    args = parser.parse_args()
    if args.base_url is None and args.rescore is None:
        parser.error("set EVALS_BASE_URL or pass --base-url http://localhost:<your backend port>")
    questions = select(questions=load_gold(), split=args.split)
    if args.only is not None:
        questions = [question for question in questions if question.id in args.only]
    computed, problems = await compute_all(questions=questions, check_paths=False)
    problems += check_frozen(questions=questions, computed=computed, frozen=load_frozen())
    if problems:
        for problem in problems:
            print(f"PROBLEM {problem}")  # noqa: T201
        return 1
    if args.rescore is not None:
        turns = earlier_turns(path=args.rescore, questions=questions)
        args.runs = 1 + max(run for _, run in turns)
    else:
        turns = await ask_all(
            questions=questions,
            base_url=str(args.base_url),
            runs=args.runs,
            concurrency=args.concurrency,
        )
    results = [
        score_turn(
            question=question,
            computed=computed[question.id],
            turn=turns[(question.id, run)],
            run=run,
        )
        for question in questions
        for run in range(args.runs)
    ]
    splits = sorted({question.split for question in questions})
    reports = {
        split: summary(results=[r for r in results if r.split == split], runs=args.runs)
        for split in splits
    }
    for split, report in reports.items():
        print(format_summary(split=split, report=report, questions=questions))  # noqa: T201
    path = write_results(split=args.split, reports=reports, results=results)
    print(f"results in {path}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
