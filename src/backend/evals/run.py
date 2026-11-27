"""Live tool-choice eval: sends each question to a running backend and checks the tool calls."""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

QUESTIONS_PATH = Path(__file__).with_name("questions.yaml")
TURN_TIMEOUT_SECONDS = 180
DEFAULT_MIN_PASS_RATE = 0.9


class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    evals_base_url: str | None = None
    banking_api_url: str = "http://localhost:8000/api"
    # A demo customer of the mock e-banking; the logins are public in starter/README.md.
    evals_username: str = "lukas"
    evals_password: str = "lukas2026"


class ExpectedCall(BaseModel):
    tool: str
    # Full-match regex per argument, ignoring case; a left-out argument counts as "".
    arguments: dict[str, str] = Field(default_factory=dict)


class Question(BaseModel):
    question: str
    # Earlier messages of the same conversation; only the calls for `question` count.
    before: list[str] = Field(default_factory=list)
    calls: list[ExpectedCall] = Field(default_factory=list)
    not_called: list[str] = Field(default_factory=list)
    # Regex the answer must contain, ignoring case, e.g. a word only its language has.
    answer: str | None = None
    # A passage of the reply to the last `before` message, quoted in `question`.
    quote: str | None = None


class ActualCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    error: str | None


def load_questions(path: Path) -> list[Question]:
    # A file with only comments loads as None.
    return [Question.model_validate(item) for item in yaml.safe_load(path.read_text()) or []]


def matches(expected: ExpectedCall, actual: ActualCall) -> bool:
    if actual.tool_name != expected.tool or actual.error is not None:
        return False
    return all(
        re.fullmatch(pattern, str(actual.arguments.get(name, "")), re.IGNORECASE) is not None
        for name, pattern in expected.arguments.items()
    )


def find_problems(question: Question, calls: list[ActualCall]) -> list[str]:
    if not question.calls:
        return ["expected no tool call"] if calls else []
    problems = [
        f"missing {expected.tool}({expected.arguments})"
        for expected in question.calls
        if not any(matches(expected=expected, actual=call) for call in calls)
    ]
    expected_tools = {expected.tool for expected in question.calls}
    for call in calls:
        if call.tool_name in question.not_called:
            problems.append(f"called {call.tool_name}, which it must not")
            continue
        is_unexpected = not any(
            matches(expected=expected, actual=call) for expected in question.calls
        )
        if call.tool_name in expected_tools and call.error is None and is_unexpected:
            problems.append(f"unexpected {call.tool_name}({call.arguments})")
    return problems


def answer_problems(question: Question, answer: str) -> list[str]:
    if question.answer is None or re.search(question.answer, answer, re.IGNORECASE) is not None:
        return []
    return [f"answer lacks /{question.answer}/: {answer[:80]!r}"]


def spelling_problems(answer: str) -> list[str]:
    # ponytail: ß only shows up in German, so no language detection is needed
    return ["answer writes ß, Swiss German uses ss"] if "ß" in answer else []


def describe(calls: list[ActualCall]) -> str:
    parts = [
        f"{call.tool_name}({call.arguments}){' FAILED' if call.error is not None else ''}"
        for call in calls
    ]
    return ", ".join(parts) or "no tool"


async def ask(client: httpx.AsyncClient, question: Question) -> tuple[list[str], str]:
    conversation = await client.post("/api/conversations", json={"title": "eval"})
    if conversation.status_code != 201:
        return [f"no conversation: {conversation.status_code} {conversation.text[:200]}"], ""
    path = f"/api/conversations/{conversation.json()['id']}"
    try:
        quotes: list[dict[str, Any]] = []
        for index, content in enumerate([*question.before, question.question]):
            earlier = await client.get(f"{path}/tool-calls")
            reply = await client.post(
                f"{path}/messages", json={"content": content, "quotes": quotes}
            )
            if reply.status_code != 201:
                return [f"turn failed: {reply.status_code} {reply.text[:200]}"], ""
            if index == len(question.before) - 1 and question.quote is not None:
                quotes = [
                    {"message_id": reply.json()["id"], "text": question.quote, "comment": None}
                ]
        response = await client.get(f"{path}/tool-calls")
        new_calls = response.json()[len(earlier.json()) :]
        calls = [ActualCall.model_validate(call) for call in new_calls]
        problems = find_problems(question=question, calls=calls)
        answer = reply.json()["content"]
        problems += answer_problems(question=question, answer=answer)
        problems += spelling_problems(answer=answer)
        return problems, describe(calls=calls)
    finally:
        await client.delete(path)


async def run_question(client: httpx.AsyncClient, question: Question) -> tuple[bool, str]:
    started = time.perf_counter()
    try:
        problems, got = await ask(client=client, question=question)
    except httpx.HTTPError as error:
        problems, got = [f"request failed: {error!r}"], ""
    is_passed = not problems
    seconds = time.perf_counter() - started
    line = f"{'ok  ' if is_passed else 'FAIL'} {seconds:5.1f}s  {question.question[:60]:60}  {got}"
    if problems:
        line += "  <- " + "; ".join(problems)
    return is_passed, line


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=EvalSettings().evals_base_url)
    parser.add_argument(
        "--min", type=float, default=DEFAULT_MIN_PASS_RATE, help="lowest pass rate that exits 0"
    )
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    args = parser.parse_args()
    if args.base_url is None:
        parser.error("set EVALS_BASE_URL or pass --base-url http://localhost:<your backend port>")
    settings = EvalSettings()
    questions = load_questions(path=args.questions)
    if not questions:
        print(f"No questions in {args.questions} yet.")  # noqa: T201
        return 0
    passed = 0
    # The e-banking issues the token our backend expects, as it does for the iframe.
    async with httpx.AsyncClient(timeout=TURN_TIMEOUT_SECONDS) as bank:
        login = await bank.post(
            f"{settings.banking_api_url}/auth/login",
            json={"username": settings.evals_username, "password": settings.evals_password},
        )
    if login.status_code != 200:
        parser.error(f"login failed: {login.status_code} {login.text[:200]}")
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=TURN_TIMEOUT_SECONDS, headers=headers
    ) as client:
        # ponytail: one question after the other, gentle on the prepaid Apertus credit
        for question in questions:
            is_passed, line = await run_question(client=client, question=question)
            passed += is_passed
            print(line, flush=True)  # noqa: T201
    rate = passed / len(questions)
    print(f"{passed} of {len(questions)} passed ({rate:.0%}), minimum {args.min:.0%}")  # noqa: T201
    return 0 if rate >= args.min else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
