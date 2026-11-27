"""One offline page with every eval result, grouped by the success criteria of the brief."""

import html
import statistics
from datetime import datetime

from pydantic import BaseModel

from evals.run import Question, QuestionResult

CUSTOMERS = ("lukas", "jana", "daniela", "marco")

OUTPUT = "output"
TRACEABILITY = "traceability"
GUARDRAILS = "guardrails"
SOVEREIGNTY = "sovereignty"


class Criterion(BaseModel):
    key: str
    title: str
    brief: str
    behind: str


CRITERIA = [
    Criterion(
        key=OUTPUT,
        title="Output fulfilment",
        brief=(
            "For the reference questions and similar requests, the TrustRoom delivers the "
            "requested type of output."
        ),
        behind=(
            "The questions of evals/questions.yaml, asked as each of the four customers: the "
            "answer has to call the tool that computes the requested output, with the right "
            "period and grouping."
        ),
    ),
    Criterion(
        key=TRACEABILITY,
        title="Traceability",
        brief="Figures are computed from the customer's data, never invented.",
        behind=(
            "The reference questions of evals/figures.yaml, each asked as its own customer: the "
            "answer has to contain the figure the bank's data gives (python -m evals.reference)."
        ),
    ),
    Criterion(
        key=SOVEREIGNTY,
        title="Data sovereignty",
        brief=(
            "The full pipeline runs with Apertus and self-hostable open-weights components only; "
            "no closed models or proprietary AI APIs at runtime."
        ),
        behind=(
            "Every question on this page that got a reply: the reply names the model that wrote "
            "it, and it has to be an Apertus model. The rest of this criterion, the self-hosted "
            "components and the data flow, is documented in the technical report."
        ),
    ),
    Criterion(
        key=GUARDRAILS,
        title="Guardrails",
        brief=(
            "No regulated investment advice, no new credit products, a pointer to free debt "
            "counselling, and the customer's own data only."
        ),
        behind=(
            "The questions of evals/guardrails.yaml, asked as the eval customer (Lukas unless "
            "EVALS_USERNAME says otherwise), because their patterns name his advisor and the other "
            "customers."
        ),
    ),
]


class PlannedQuestion(BaseModel):
    criterion: str
    question: Question


class Entry(BaseModel):
    criterion: str
    result: QuestionResult


def plan_questions(
    tool_choice: list[Question], figures: list[Question], guardrails: list[Question]
) -> list[PlannedQuestion]:
    planned = [
        PlannedQuestion(criterion=OUTPUT, question=question.model_copy(update={"customer": name}))
        for question in tool_choice
        for name in (CUSTOMERS if question.customer is None else (question.customer,))
    ]
    planned += [PlannedQuestion(criterion=TRACEABILITY, question=item) for item in figures]
    planned += [PlannedQuestion(criterion=GUARDRAILS, question=item) for item in guardrails]
    return planned


def sovereignty_problems(result: QuestionResult) -> list[str]:
    if result.model is None:
        return ["the reply names no model"]
    if "apertus" not in result.model.lower():
        return [f"written by {result.model}"]
    return []


def problems_for(criterion: str, result: QuestionResult) -> list[str]:
    if criterion == SOVEREIGNTY:
        return sovereignty_problems(result=result)
    return result.problems


def results_for(criterion: str, entries: list[Entry]) -> list[QuestionResult]:
    if criterion == SOVEREIGNTY:
        # A turn that got no reply has no model to check; its own criterion shows why.
        return [entry.result for entry in entries if entry.result.got != ""]
    return [entry.result for entry in entries if entry.criterion == criterion]


def question_key(question: Question) -> str:
    return "\n".join([*question.before, question.question])


def _text(value: str) -> str:
    return html.escape(value, quote=True)


def _rate(passed: int, total: int) -> str:
    if total == 0:
        return '<td class="none">-</td>'
    css = "good" if passed == total else "bad" if passed / total < 0.8 else "mid"
    return f'<td class="{css}">{passed} of {total} <small>{passed / total:.0%}</small></td>'


def _seconds(values: list[float]) -> str:
    return f"{statistics.median(values):.1f} s / {max(values):.1f} s"


def _summary(entries: list[Entry]) -> str:
    header = "".join(f"<th>{name.capitalize()}</th>" for name in CUSTOMERS)
    rows = []
    for criterion in CRITERIA:
        results = results_for(criterion=criterion.key, entries=entries)
        cells = ""
        for name in [*CUSTOMERS, None]:
            mine = [result for result in results if name is None or result.customer == name]
            failed = sum(
                1 for result in mine if problems_for(criterion=criterion.key, result=result) != []
            )
            cells += _rate(passed=len(mine) - failed, total=len(mine))
        rows.append(f'<tr><th><a href="#{criterion.key}">{criterion.title}</a></th>{cells}</tr>')
    timing = ""
    for name in [*CUSTOMERS, None]:
        seconds = [
            entry.result.seconds
            for entry in entries
            if name is None or entry.result.customer == name
        ]
        timing += (
            f"<td>{_seconds(values=seconds)}</td>" if seconds != [] else '<td class="none">-</td>'
        )
    performance = '<a href="#performance">Performance</a> <small>median / slowest</small>'
    rows.append(f"<tr><th>{performance}</th>{timing}</tr>")
    return (
        f'<table class="summary"><tr><th>Criterion</th>{header}<th>All</th></tr>'
        f"{''.join(rows)}</table>"
    )


def _grid(criterion: Criterion, entries: list[Entry]) -> str:
    results = results_for(criterion=criterion.key, entries=entries)
    by_question: dict[str, list[QuestionResult]] = {}
    for result in results:
        by_question.setdefault(question_key(question=result.question), []).append(result)
    header = "".join(f"<th>{name.capitalize()}</th>" for name in CUSTOMERS)
    rows = []
    for key, asked in by_question.items():
        rule = asked[0].question.rule
        label = _text(value=key) + (
            f' <span class="rule">{_text(value=rule)}</span>' if rule is not None else ""
        )
        cells = ""
        for name in CUSTOMERS:
            mine = [result for result in asked if result.customer == name]
            if mine == []:
                cells += '<td class="none">-</td>'
                continue
            failed = any(
                problems_for(criterion=criterion.key, result=result) != [] for result in mine
            )
            seconds = ", ".join(f"{result.seconds:.0f} s" for result in mine)
            cells += (
                f'<td class="{"bad" if failed else "good"}">{"fail" if failed else "pass"} '
                f"<small>{seconds}</small></td>"
            )
        cells += f"<td>{_seconds(values=[result.seconds for result in asked])}</td>"
        rows.append(f'<tr><td class="question">{label}</td>{cells}</tr>')
    return (
        f'<table class="grid"><tr><th>Question</th>{header}<th>Median / slowest</th></tr>'
        f"{''.join(rows)}</table>"
    )


def _failures(criterion: Criterion, entries: list[Entry]) -> str:
    items = []
    for result in results_for(criterion=criterion.key, entries=entries):
        problems = problems_for(criterion=criterion.key, result=result)
        if problems == []:
            continue
        got = result.got if result.got != "" else "none"
        items.append(
            f"<li><b>{result.customer.capitalize()}</b>: {_text(value=result.question.question)}"
            f'<div class="reason">{_text(value="; ".join(problems))}</div>'
            f'<div class="got">Tools called: {_text(value=got)}</div></li>'
        )
    if items == []:
        return '<p class="none">No failures.</p>'
    return f'<h3>Failures and their reasons</h3><ul class="failures">{"".join(items)}</ul>'


def _section(criterion: Criterion, entries: list[Entry]) -> str:
    return (
        f'<section id="{criterion.key}"><h2>{criterion.title}</h2>'
        f"<blockquote>{_text(value=criterion.brief)}</blockquote>"
        f"<p><b>Behind the number:</b> {_text(value=criterion.behind)}</p>"
        f"{_grid(criterion=criterion, entries=entries)}"
        f"{_failures(criterion=criterion, entries=entries)}</section>"
    )


def _performance(entries: list[Entry]) -> str:
    by_question: dict[str, list[float]] = {}
    for entry in entries:
        key = question_key(question=entry.result.question)
        by_question.setdefault(key, []).append(entry.result.seconds)
    ranked = sorted(by_question.items(), key=lambda item: max(item[1]), reverse=True)
    rows = "".join(
        f'<tr><td class="question">{_text(value=key)}</td><td>{len(seconds)}</td>'
        f"<td>{statistics.median(seconds):.1f}</td><td>{max(seconds):.1f}</td></tr>"
        for key, seconds in ranked
    )
    return (
        '<section id="performance"><h2>Performance</h2>'
        "<blockquote>Acceptable response times with Apertus v1.5 8B or 70B on the provided "
        "infrastructure.</blockquote>"
        "<p><b>Behind the number:</b> every question on this page, slowest first. The seconds are "
        "the wall time of the whole question, with uploads and earlier turns of the same "
        "conversation.</p>"
        '<table class="grid"><tr><th>Question</th><th>Asked</th><th>Median s</th>'
        f"<th>Slowest s</th></tr>{rows}</table></section>"
    )


STYLE = """
:root { --bg: #fff; --fg: #1d2330; --muted: #5d6675; --line: #dde1e7; --good: #e3f4e8;
  --good-fg: #1d6b38; --mid: #fdf3d8; --mid-fg: #7a5a00; --bad: #fbe4e4; --bad-fg: #a12b2b; }
@media (prefers-color-scheme: dark) { :root { --bg: #14171c; --fg: #e8eaee; --muted: #9aa3b0;
  --line: #2c323b; --good: #17331f; --good-fg: #8fd6a4; --mid: #3a3115; --mid-fg: #e8c66a;
  --bad: #3d1d1d; --bad-fg: #f0a0a0; } }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { margin: 0 0 4px; } h2 { margin-top: 48px; border-bottom: 1px solid var(--line); }
.meta, small, .none, .got { color: var(--muted); }
blockquote { margin: 8px 0; padding-left: 12px; border-left: 3px solid var(--line); }
table { border-collapse: collapse; width: 100%; margin: 12px 0; display: block; overflow-x: auto; }
th, td { border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left;
  vertical-align: top; white-space: nowrap; }
td.question { white-space: pre-wrap; min-width: 280px; }
.good { background: var(--good); color: var(--good-fg); }
.mid { background: var(--mid); color: var(--mid-fg); }
.bad { background: var(--bad); color: var(--bad-fg); }
.rule { font-size: 12px; padding: 1px 6px; border: 1px solid var(--line); border-radius: 8px; }
.failures li { margin-bottom: 10px; white-space: pre-wrap; }
.reason { color: var(--bad-fg); }
a { color: inherit; }
"""


def render_page(entries: list[Entry], base_url: str, finished_at: datetime) -> str:
    models = sorted({entry.result.model for entry in entries if entry.result.model is not None})
    sections = "".join(_section(criterion=criterion, entries=entries) for criterion in CRITERIA)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>TrustRoom evals</title><style>{STYLE}</style></head><body><main>"
        "<h1>TrustRoom evals</h1>"
        f'<p class="meta">{len(entries)} questions against {_text(value=base_url)}, finished '
        f"{finished_at:%d.%m.%Y %H:%M}. Models that answered: "
        f"{_text(value=', '.join(models) if models != [] else 'none')}.</p>"
        f"{_summary(entries=entries)}{sections}{_performance(entries=entries)}"
        "</main></body></html>"
    )
