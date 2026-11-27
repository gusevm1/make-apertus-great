"""Live tool-choice eval: sends each question to a running backend and checks the tool calls."""

import argparse
import asyncio
import re
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

QUESTIONS_PATH = Path(__file__).with_name("questions.yaml")
GUARDRAILS_PATH = Path(__file__).with_name("guardrails.yaml")
FIGURES_PATH = Path(__file__).with_name("figures.yaml")
DOCUMENTS_PATH = Path(__file__).resolve().parents[3] / "starter/resources/Demodaten/Dokumente"
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
    # True leaves the calls unchecked, except for `not_called`.
    any_calls: bool = False
    not_called: list[str] = Field(default_factory=list)
    # Regex the answer must contain, ignoring case, e.g. a word only its language has.
    answer: str | None = None
    # Regex the answer must not contain, ignoring case.
    answer_not: str | None = None
    # Groups questions in the summary, e.g. the guardrail a question tests.
    rule: str | None = None
    # A passage of the reply to the last `before` message, quoted in `question`.
    quote: str | None = None
    # The demo login the question runs as; None is the eval customer from the settings.
    customer: str | None = None
    # Sample documents under DOCUMENTS_PATH, uploaded and attached to `question`.
    documents: list[str] = Field(default_factory=list)


class ActualCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    error: str | None


class Answer(BaseModel):
    problems: list[str]
    got: str = ""
    # The model the backend names in the reply's provenance; None when the turn failed or had none.
    model: str | None = None


class QuestionResult(BaseModel):
    question: Question
    customer: str
    problems: list[str]
    got: str
    model: str | None
    # Wall time of the whole question, with uploads and the `before` turns.
    seconds: float

    @property
    def is_passed(self) -> bool:
        return not self.problems


def password_for(customer: str, settings: EvalSettings) -> str:
    # The demo logins in starter/README.md follow one pattern, such as jana / jana2026.
    if customer == settings.evals_username:
        return settings.evals_password
    return f"{customer}2026"


async def log_in(bank: httpx.AsyncClient, customer: str, settings: EvalSettings) -> str:
    login = await bank.post(
        f"{settings.banking_api_url}/auth/login",
        json={"username": customer, "password": password_for(customer=customer, settings=settings)},
    )
    login.raise_for_status()
    return login.json()["token"]


def load_questions(path: Path) -> list[Question]:
    # A file with only comments loads as None; a mapping holds shared patterns beside `questions`.
    content = yaml.safe_load(path.read_text()) or []
    items = content["questions"] if isinstance(content, dict) else content
    return [Question.model_validate(item) for item in items]


def matches(expected: ExpectedCall, actual: ActualCall) -> bool:
    if actual.tool_name != expected.tool or actual.error is not None:
        return False
    return all(
        re.fullmatch(pattern, str(actual.arguments.get(name, "")), re.IGNORECASE) is not None
        for name, pattern in expected.arguments.items()
    )


def find_problems(question: Question, calls: list[ActualCall]) -> list[str]:
    problems = [
        f"called {call.tool_name}, which it must not"
        for call in calls
        if call.tool_name in question.not_called
    ]
    if question.any_calls:
        return problems
    if not question.calls:
        return ["expected no tool call"] if calls else []
    problems += [
        f"missing {expected.tool}({expected.arguments})"
        for expected in question.calls
        if not any(matches(expected=expected, actual=call) for call in calls)
    ]
    expected_tools = {expected.tool for expected in question.calls}
    for call in calls:
        if call.tool_name in question.not_called:
            continue
        is_unexpected = not any(
            matches(expected=expected, actual=call) for expected in question.calls
        )
        if call.tool_name in expected_tools and call.error is None and is_unexpected:
            problems.append(f"unexpected {call.tool_name}({call.arguments})")
    return problems


def answer_problems(question: Question, answer: str) -> list[str]:
    problems = []
    if question.answer is not None and re.search(question.answer, answer, re.IGNORECASE) is None:
        problems.append(f"answer lacks /{question.answer}/: {answer[:80]!r}")
    if question.answer_not is not None:
        found = re.search(question.answer_not, answer, re.IGNORECASE)
        if found is not None:
            problems.append(f"answer contains {found.group(0)!r}")
    return problems


def spelling_problems(answer: str) -> list[str]:
    # ponytail: ß only shows up in German, so no language detection is needed
    return ["answer writes ß, Swiss German uses ss"] if "ß" in answer else []


def describe(calls: list[ActualCall]) -> str:
    parts = [
        f"{call.tool_name}({call.arguments}){' FAILED' if call.error is not None else ''}"
        for call in calls
    ]
    return ", ".join(parts) or "no tool"


async def delete_proposals(client: httpx.AsyncClient, conversation_path: str) -> None:
    # Deleting the conversation empties source_id, so this runs first.
    tool_calls = (await client.get(f"{conversation_path}/tool-calls")).raise_for_status()
    call_ids = {call["id"] for call in tool_calls.json()}
    proposals = await client.get("/api/context-entries", params={"status": "proposed"})
    for entry in proposals.raise_for_status().json():
        if entry["source_id"] in call_ids:
            (await client.delete(f"/api/context-entries/{entry['id']}")).raise_for_status()


async def ask(client: httpx.AsyncClient, question: Question) -> Answer:
    conversation = await client.post("/api/conversations", json={"title": "eval"})
    if conversation.status_code != 201:
        return Answer(
            problems=[f"no conversation: {conversation.status_code} {conversation.text[:200]}"]
        )
    path = f"/api/conversations/{conversation.json()['id']}"
    document_ids: list[str] = []
    try:
        for name in question.documents:
            file = DOCUMENTS_PATH / name
            upload = await client.post(
                "/api/documents", files={"file": (file.name, file.read_bytes(), "application/pdf")}
            )
            if upload.status_code != 201:
                return Answer(
                    problems=[f"upload of {name} failed: {upload.status_code} {upload.text[:200]}"]
                )
            document_ids.append(upload.json()["id"])
        quotes: list[dict[str, Any]] = []
        messages = [*question.before, question.question]
        for index, content in enumerate(messages):
            earlier = await client.get(f"{path}/tool-calls")
            attached = document_ids if index == len(messages) - 1 else []
            reply = await client.post(
                f"{path}/messages",
                json={"content": content, "quotes": quotes, "document_ids": attached},
            )
            if reply.status_code != 201:
                return Answer(problems=[f"turn failed: {reply.status_code} {reply.text[:200]}"])
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
        provenance = reply.json()["provenance"]
        return Answer(
            problems=problems,
            got=describe(calls=calls),
            model=None if provenance is None else provenance["model"],
        )
    finally:
        await delete_proposals(client=client, conversation_path=path)
        await client.delete(path)
        for document_id in document_ids:
            await client.delete(f"/api/documents/{document_id}")


async def run_question(
    client: httpx.AsyncClient, question: Question, customer: str
) -> QuestionResult:
    started = time.perf_counter()
    try:
        answer = await ask(client=client, question=question)
    except httpx.HTTPError as error:
        answer = Answer(problems=[f"request failed: {error!r}"])
    return QuestionResult(
        question=question,
        customer=customer,
        problems=answer.problems,
        got=answer.got,
        model=answer.model,
        seconds=time.perf_counter() - started,
    )


def format_result(result: QuestionResult) -> str:
    line = (
        f"{'ok  ' if result.is_passed else 'FAIL'} {result.seconds:5.1f}s  "
        f"{result.question.question[:60]:60}  {result.got}"
    )
    if result.problems:
        line += "  <- " + "; ".join(result.problems)
    return line


async def run_questions(
    questions: list[Question], base_url: str, settings: EvalSettings
) -> AsyncIterator[QuestionResult]:
    # The e-banking issues the token our backend expects, as it does for the iframe.
    tokens: dict[str, str] = {}
    async with (
        httpx.AsyncClient(timeout=TURN_TIMEOUT_SECONDS) as bank,
        httpx.AsyncClient(base_url=base_url, timeout=TURN_TIMEOUT_SECONDS) as client,
    ):
        # ponytail: one question after the other, gentle on the prepaid Apertus credit
        for question in questions:
            customer = settings.evals_username if question.customer is None else question.customer
            if customer not in tokens:
                try:
                    tokens[customer] = await log_in(bank=bank, customer=customer, settings=settings)
                except httpx.HTTPError as error:
                    raise SystemExit(f"login as {customer} failed: {error!r}") from error
            client.headers["Authorization"] = f"Bearer {tokens[customer]}"
            yield await run_question(client=client, question=question, customer=customer)


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
    passed_by_rule: dict[str, list[bool]] = {}
    async for result in run_questions(
        questions=questions, base_url=args.base_url, settings=settings
    ):
        passed += result.is_passed
        if result.question.rule is not None:
            passed_by_rule.setdefault(result.question.rule, []).append(result.is_passed)
        print(format_result(result=result), flush=True)  # noqa: T201
    for rule, results in passed_by_rule.items():
        print(f"{rule}: {sum(results)} of {len(results)}")  # noqa: T201
    rate = passed / len(questions)
    print(f"{passed} of {len(questions)} passed ({rate:.0%}), minimum {args.min:.0%}")  # noqa: T201
    return 0 if rate >= args.min else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
