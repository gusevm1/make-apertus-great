import re
from datetime import datetime

from evals.report import (
    CUSTOMERS,
    GUARDRAILS,
    OUTPUT,
    SOVEREIGNTY,
    TRACEABILITY,
    Entry,
    plan_questions,
    render_page,
    sovereignty_problems,
)
from evals.run import (
    FIGURES_PATH,
    GUARDRAILS_PATH,
    QUESTIONS_PATH,
    Question,
    QuestionResult,
    load_questions,
)


def result(
    question: str,
    customer: str = "lukas",
    problems: list[str] | None = None,
    model: str | None = "apertus-v1-5-70b",
    seconds: float = 10.0,
) -> QuestionResult:
    return QuestionResult(
        question=Question(question=question, customer=customer),
        customer=customer,
        problems=[] if problems is None else problems,
        got="sum_by_month({})",
        model=model,
        seconds=seconds,
    )


def page(entries: list[Entry]) -> str:
    return render_page(
        entries=entries, base_url="http://localhost:8010", finished_at=datetime(2026, 11, 27, 9, 0)
    )


def section(html: str, criterion: str) -> str:
    return html.split(f'<section id="{criterion}">')[1].split("</section>")[0]


def test_tool_choice_runs_as_every_customer_and_the_rest_as_written() -> None:
    planned = plan_questions(
        tool_choice=load_questions(path=QUESTIONS_PATH),
        figures=load_questions(path=FIGURES_PATH),
        guardrails=load_questions(path=GUARDRAILS_PATH),
    )

    tool_choice = [item.question for item in planned if item.criterion == OUTPUT]
    figures = [item.question for item in planned if item.criterion == TRACEABILITY]
    guardrails = [item.question for item in planned if item.criterion == GUARDRAILS]
    # A question that names its customer runs as that customer only.
    assert len(tool_choice) == sum(
        len(CUSTOMERS) if question.customer is None else 1
        for question in load_questions(path=QUESTIONS_PATH)
    )
    assert {question.customer for question in tool_choice} == set(CUSTOMERS)
    assert figures == load_questions(path=FIGURES_PATH)
    assert all(question.customer is None for question in guardrails)


def test_each_criterion_counts_its_own_questions_per_customer() -> None:
    html = page(
        entries=[
            Entry(criterion=OUTPUT, result=result(question="Monthly spending?", customer="jana")),
            Entry(
                criterion=OUTPUT,
                result=result(question="Monthly spending?", customer="marco", problems=["x"]),
            ),
            Entry(criterion=TRACEABILITY, result=result(question="Online shops?")),
        ]
    )

    summary = html.split('<table class="summary">')[1].split("</table>")[0]
    output_row = summary.split('href="#output"')[1].split("</tr>")[0]
    assert re.findall(r">(\d+ of \d+|-)[ <]", output_row) == [
        "-",
        "1 of 1",
        "-",
        "0 of 1",
        "1 of 2",
    ]
    assert "Monthly spending?" not in section(html=html, criterion=TRACEABILITY)


def test_a_failure_shows_its_reason_escaped() -> None:
    reason = "answer lacks /1'210.60/: '<script>alert(1)</script>'"
    html = page(
        entries=[
            Entry(criterion=TRACEABILITY, result=result(question="Online?", problems=[reason]))
        ]
    )

    failures = section(html=html, criterion=TRACEABILITY)
    assert "answer lacks /1&#x27;210.60/" in failures
    assert "<script>" not in html
    assert "&lt;script&gt;" in failures


def test_the_page_loads_nothing_from_outside() -> None:
    html = page(entries=[Entry(criterion=GUARDRAILS, result=result(question="Soll ich SARON?"))])

    assert re.search(r"(src|href)=\"?https?:", html) is None
    assert "<link" not in html


def test_performance_lists_median_and_slowest_per_question() -> None:
    html = page(
        entries=[
            Entry(criterion=OUTPUT, result=result(question="Weekends?", customer=name, seconds=s))
            for name, s in zip(CUSTOMERS, [4.0, 6.0, 8.0, 30.0], strict=True)
        ]
    )

    assert "<td>4</td><td>7.0</td><td>30.0</td>" in section(html=html, criterion="performance")


def test_sovereignty_needs_an_apertus_model_on_every_reply() -> None:
    assert sovereignty_problems(result=result(question="Hi")) == []
    assert sovereignty_problems(result=result(question="Hi", model="gpt-4o")) == [
        "written by gpt-4o"
    ]
    assert sovereignty_problems(result=result(question="Hi", model=None)) == [
        "the reply names no model"
    ]


def test_a_turn_without_reply_is_left_out_of_sovereignty() -> None:
    failed = result(question="Hi", model=None, problems=["turn failed: 502"])
    failed.got = ""
    html = page(entries=[Entry(criterion=OUTPUT, result=failed)])

    assert "the reply names no model" not in section(html=html, criterion=SOVEREIGNTY)
    assert "turn failed: 502" in section(html=html, criterion=OUTPUT)
