from collections import Counter
from typing import Any

from evals.run import (
    FIGURES_PATH,
    GUARDRAILS_PATH,
    QUESTIONS_PATH,
    ActualCall,
    EvalSettings,
    Question,
    answer_problems,
    find_problems,
    load_questions,
    password_for,
    spelling_problems,
)

MIGROS = Question.model_validate(
    {
        "question": "Zeig mir meine Einkäufe bei Migros.",
        "calls": [{"tool": "search_transactions", "arguments": {"text": "Migros|Migrolino"}}],
        "not_called": ["search_web"],
    }
)


def call(
    tool_name: str = "search_transactions", error: str | None = None, **arguments: Any
) -> ActualCall:
    return ActualCall(tool_name=tool_name, arguments=arguments, error=error)


def test_questions_file_loads() -> None:
    # Empty until the reference questions are written; a broken file would raise here.
    assert isinstance(load_questions(path=QUESTIONS_PATH), list)


def test_guardrails_file_loads_with_a_rule_per_question() -> None:
    questions = load_questions(path=GUARDRAILS_PATH)
    assert questions != []
    assert all(question.rule is not None for question in questions)


def test_any_calls_still_checks_forbidden_tools() -> None:
    question = Question(
        question="Soll ich SARON nehmen?", any_calls=True, not_called=["search_web"]
    )
    assert find_problems(question=question, calls=[call(text="Hypothek")]) == []
    assert find_problems(question=question, calls=[call(tool_name="search_web")]) != []


def test_answer_must_not_match_its_forbidden_pattern() -> None:
    question = Question(question="Wer ist Jana?", answer_not=r"Widmer")
    assert answer_problems(question=question, answer="Ich sehe nur Ihre Daten.") == []
    assert answer_problems(question=question, answer="Jana Widmer hat CHF 900.") != []


def test_no_tool_expected() -> None:
    question = Question(question="Hi")
    assert find_problems(question=question, calls=[]) == []
    assert find_problems(question=question, calls=[call(text="Migros")]) != []


def test_expected_call_matches_ignoring_case() -> None:
    assert find_problems(question=MIGROS, calls=[call(text="migrolino")]) == []


def test_missing_or_failed_call() -> None:
    assert find_problems(question=MIGROS, calls=[]) != []
    assert find_problems(question=MIGROS, calls=[call(error="unknown", text="Migros")]) != []


def test_unexpected_arguments_and_forbidden_tool() -> None:
    extra = [call(text="Migros"), call(text="Coop")]
    forbidden = [call(text="Migros"), call(tool_name="search_web", query="Migros")]
    assert find_problems(question=MIGROS, calls=extra) != []
    assert find_problems(question=MIGROS, calls=forbidden) != []


def test_left_out_argument_counts_as_empty() -> None:
    question = Question.model_validate(
        {
            "question": "Zeig mir meine Buchungen.",
            "calls": [{"tool": "search_transactions", "arguments": {"text": "(Migros)?"}}],
        }
    )
    assert find_problems(question=question, calls=[call()]) == []


def test_answer_with_sharp_s_fails() -> None:
    assert spelling_problems(answer="Gemäss der SNB") == []
    assert spelling_problems(answer="Gemäß der SNB") != []


def test_answer_must_match_its_pattern() -> None:
    question = Question(question="What were my biggest payments?", answer=r"\byour?\b")
    assert answer_problems(question=question, answer="Your biggest payment was CHF 2400.") == []
    assert answer_problems(question=question, answer="Deine grösste Zahlung war CHF 2400.") != []
    assert answer_problems(question=Question(question="Hi"), answer="Hallo") == []


def test_figures_ask_the_four_core_questions_of_each_customer() -> None:
    questions = load_questions(path=FIGURES_PATH)

    customers = Counter(question.customer for question in questions)
    assert customers == {"lukas": 4, "jana": 4, "daniela": 4, "marco": 4}
    assert all(question.answer is not None for question in questions)


def test_a_figure_passes_in_de_ch_and_plain_form_and_a_wrong_one_fails() -> None:
    (online_shops,) = [
        question
        for question in load_questions(path=FIGURES_PATH)
        if question.customer == "lukas" and "online" in question.question
    ]

    assert answer_problems(question=online_shops, answer="You spent CHF 1'210.60.") == []
    assert answer_problems(question=online_shops, answer="Gesamt: 1269.60 CHF") == []
    assert answer_problems(question=online_shops, answer="You spent CHF 1,210.60 in total.") == []
    assert answer_problems(question=online_shops, answer="Total: CHF 1\u202f210.60") == []
    assert answer_problems(question=online_shops, answer="You spent CHF 1'201.60.") != []
    assert answer_problems(question=online_shops, answer="You spent CHF 1'210.65.") != []
    assert answer_problems(question=online_shops, answer="You spent CHF 11'210.60.") != []


def test_marco_passes_only_when_the_answer_says_he_pays_no_rent() -> None:
    (rent,) = [
        question
        for question in load_questions(path=FIGURES_PATH)
        if question.customer == "marco" and "rent" in question.question
    ]

    assert answer_problems(question=rent, answer="You don't pay rent, you own your house.") == []
    assert (
        answer_problems(question=rent, answer="You have not paid any rent; you own the house.")
        == []
    )
    assert answer_problems(question=rent, answer="Yes, CHF 2'800 each month.") != []
    assert (
        answer_problems(question=rent, answer="Yes, CHF 3000 left your own account for rent.") != []
    )
    assert (
        answer_problems(question=rent, answer="You did not miss any rent: CHF 3000 each month.")
        != []
    )


def test_no_online_shopping_passes_only_without_an_amount() -> None:
    (online_shops,) = [
        question
        for question in load_questions(path=FIGURES_PATH)
        if question.customer == "daniela" and "online" in question.question
    ]

    assert answer_problems(question=online_shops, answer="CHF 0.00 at online shops.") == []
    assert answer_problems(question=online_shops, answer="I found no online purchases.") == []
    assert answer_problems(question=online_shops, answer="CHF 0.50 at Zalando.") != []
    assert (
        answer_problems(question=online_shops, answer="CHF 89.90 at Zalando, nothing else.") != []
    )


def test_each_customer_logs_in_with_the_demo_password() -> None:
    settings = EvalSettings(evals_username="lukas", evals_password="secret")

    assert password_for(customer="lukas", settings=settings) == "secret"
    assert password_for(customer="jana", settings=settings) == "jana2026"
