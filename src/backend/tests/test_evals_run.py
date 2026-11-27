from typing import Any

from evals.run import (
    QUESTIONS_PATH,
    ActualCall,
    Question,
    answer_problems,
    find_problems,
    load_questions,
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
