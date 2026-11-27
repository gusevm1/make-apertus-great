import json
import os
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx2
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings

FAKE_REPLY = "Fake reply"
FAKE_MODEL = "fake-smart"
NO_TOOL_DECISION = '{"plan": "Nothing to look up.", "calls": []}'
GUARDRAIL_SCHEMA = "GuardrailCheck"
OK_GUARDRAIL = '{"category": "ok", "language": "en"}'
ADVISOR_NAME = "Nadine Frei"
ADVISOR_PHONE = "+41 44 555 01 23"
FAKE_USAGE = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}

# Apertus is faked for now (no API key yet), so tests need no Apertus values in the environment.
os.environ |= {
    "LLM_BASE_URL": "http://apertus.invalid/v1",
    "LLM_API_KEY": "test",
    "LLM_NAME_FAST": "fake-fast",
    "LLM_NAME": FAKE_MODEL,
    "APERTUS_MAX_RETRIES": "0",
    "BANKING_API_URL": "http://banking.invalid/api",
    "OCR_URL": "http://ocr.invalid",
    "SEARXNG_URL": "http://searxng.invalid",
}

# Tests truncate every table, so they only ever run against the test DB.
# Set before app.core.db creates the engine.
test_database_url = Settings().test_database_url  # pyright: ignore[reportCallIssue]
if not test_database_url or test_database_url == os.environ.get("DATABASE_URL"):
    raise RuntimeError("Set TEST_DATABASE_URL to a database other than DATABASE_URL")
os.environ["DATABASE_URL"] = test_database_url

from app.clients.apertus import ApertusClient  # noqa: E402
from app.clients.banking import BankingClient  # noqa: E402
from app.clients.ocr import OcrClient  # noqa: E402
from app.clients.searxng import SearxngClient  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, engine, session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    command.upgrade(Config(Path(__file__).parents[1] / "alembic.ini"), "head")


@pytest.fixture(autouse=True)
async def clean_db() -> AsyncIterator[None]:
    yield
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@dataclass
class FakeApertus:
    """The fake Apertus API: `requests` is what it got, `status` fails it, `decisions` script it.

    `reply` is the text of every answer.
    Guardrail checks are kept apart: `guardrail_requests` and the `guardrails` script.
    """

    requests: list[dict[str, Any]] = field(default_factory=list)
    status: int = 200
    decisions: list[str] = field(default_factory=list)
    reply: str = FAKE_REPLY
    guardrail_requests: list[dict[str, Any]] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    # Answers a structured request from its body; without it `decisions` answer.
    structured_reply: Callable[[dict[str, Any]], str] | None = None


@pytest.fixture
def apertus() -> FakeApertus:
    return FakeApertus()


def _fake_completion(body: dict[str, Any], content: str) -> httpx2.Response:
    if body.get("stream"):
        chunks: list[dict[str, Any]] = [
            {"choices": [{"index": 0, "delta": {"content": word}}]}
            for word in re.findall(r"\S+\s*", content)
        ]
        chunks.append({"choices": [], "usage": FAKE_USAGE})
        events = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
        return httpx2.Response(
            200, text=f"{events}data: [DONE]\n\n", headers={"content-type": "text/event-stream"}
        )
    message = {"role": "assistant", "content": content}
    choice = {"index": 0, "finish_reason": "stop", "message": message}
    return httpx2.Response(200, json={"choices": [choice], "usage": FAKE_USAGE})


@dataclass
class FakeSearxng:
    """The fake SearXNG: `requests` is what it got, `status` fails it, `results` answer it."""

    requests: list[dict[str, str]] = field(default_factory=list)
    status: int = 200
    results: list[dict[str, Any]] = field(default_factory=list)
    unresponsive_engines: list[list[str]] = field(default_factory=list)


@pytest.fixture
def searxng() -> FakeSearxng:
    return FakeSearxng()


@pytest.fixture
def searxng_client(searxng: FakeSearxng) -> SearxngClient:
    """A SearXNG client faked at the HTTP level."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        searxng.requests.append(dict(request.url.params))
        if searxng.status != 200:
            return httpx2.Response(searxng.status, text="fake failure")
        body = {"results": searxng.results, "unresponsive_engines": searxng.unresponsive_engines}
        return httpx2.Response(200, json=body)

    fake_http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    return SearxngClient(settings=get_settings(), http_client=fake_http)


CUSTOMER_TOKEN = "customer-token"
CUSTOMER_ID = "CUST-001"
TODAY = date(2026, 11, 27)
ACCOUNTS = [
    {
        "account_id": "ACC-PRIV",
        "name": "Privatkonto",
        "type": "current",
        "iban": "CH06 0888 8000 0044 1002 0",
        "current_balance_chf": 9716.33,
    },
    {
        "account_id": "ACC-TAX",
        "name": "Sparkonto Steuern",
        "type": "savings",
        "iban": "CH14 0888 8000 0044 1113 7",
        "current_balance_chf": 4638.04,
    },
]


BOOKINGS = [
    {
        "booking_id": "BK-00101",
        "account_id": "ACC-PRIV",
        "booking_date": "2026-10-30",
        "amount": -212.1,
        "booking_text": "Kartenzahlung Debit Mastercard 30.10.2026 MIGROS",
        "counterparty_name": "Migros",
        "counterparty_iban": None,
        "transaction_type": "debit_card",
    },
    {
        "booking_id": "BK-00102",
        "account_id": "ACC-PRIV",
        "booking_date": "2026-10-28",
        "amount": -2800.0,
        "booking_text": "Dauerauftrag Wohnbau Sihlfeld AG",
        "counterparty_name": "Wohnbau Sihlfeld AG",
        "counterparty_iban": "CH93 0076 2011 6238 5295 7",
        "transaction_type": "standing_order",
    },
]
# The query strings the fake bank got for /bookings, newest last.
BANKING_QUERIES: list[str] = []
# Every request but a GET the fake bank got, as (method, path, JSON body or None), newest last.
BANK_WRITES: list[tuple[str, str, Any]] = []
# A payment that was already paid, so the bank refuses to change it.
COMPLETED_PAYMENT_ID = "PAY-0001"


@pytest.fixture(autouse=True)
def no_bank_writes() -> None:
    BANK_WRITES.clear()


def _fake_bank_write(request: httpx2.Request) -> httpx2.Response:
    """Payments and standing orders, answered the way the banking API does."""
    body: dict[str, Any] | None = json.loads(request.content) if request.content else None
    path = request.url.path.removeprefix("/api")
    BANK_WRITES.append((request.method, path, body))
    collection, _, item_id = path.removeprefix("/").partition("/")
    id_field = {"payments": "payment_id", "standing-orders": "standing_order_id"}.get(collection)
    if id_field is None:
        return httpx2.Response(404, json={"detail": "Not found"})
    if item_id == COMPLETED_PAYMENT_ID:
        return httpx2.Response(409, json={"detail": "Payment is not pending"})
    if body is None:
        return httpx2.Response(204)
    if request.method == "POST":
        return httpx2.Response(201, json={id_field: "NEW-1", **body})
    return httpx2.Response(200, json={id_field: item_id, **body})


def fake_banking_client() -> BankingClient:
    """A banking client faked at the HTTP level: one customer, known by `CUSTOMER_TOKEN`."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/system/info":
            return httpx2.Response(200, json={"today": TODAY.isoformat()})
        if request.headers.get("authorization") != f"Bearer {CUSTOMER_TOKEN}":
            return httpx2.Response(401, json={"detail": "Not authenticated"})
        if request.url.path == "/api/customer":
            return httpx2.Response(
                200,
                json={
                    "customer_id": CUSTOMER_ID,
                    "advisor": {"name": ADVISOR_NAME, "phone": ADVISOR_PHONE},
                },
            )
        if request.url.path == "/api/documents" and request.method == "POST":
            return httpx2.Response(201, json={"id": "DOC-0001"})
        if request.method != "GET":
            return _fake_bank_write(request=request)
        if request.url.path == "/api/bookings":
            BANKING_QUERIES.append(str(request.url.query, "ascii"))
            offset = int(request.url.params.get("offset", 0))
            return httpx2.Response(200, json={"items": BOOKINGS[offset:], "total": len(BOOKINGS)})
        if request.url.path in ("/api/cards", "/api/loan-transactions"):
            return httpx2.Response(200, json={"items": []})
        if request.url.path == "/api/accounts/ACC-PRIV/balance-preview":
            return httpx2.Response(200, json={"account_id": "ACC-PRIV", "points": []})
        if request.url.path == "/api/accounts":
            return httpx2.Response(200, json={"items": ACCOUNTS})
        return httpx2.Response(404, json={"detail": "Not found"})

    fake_http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().banking_api_url
    )
    return BankingClient(settings=get_settings(), http_client=fake_http)


OCR_MARKDOWN = "## Lohnabrechnung November 2026\n\nNettolohn CHF 7'412.55"


def fake_ocr_client(markdown: str = OCR_MARKDOWN) -> OcrClient:
    """An OCR client faked at the HTTP level: every file reads as `markdown`."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if b".exe" in request.content:
            return httpx2.Response(422, json={"detail": "Unsupported file type"})
        return httpx2.Response(200, json={"filename": "file", "markdown": markdown})

    fake_http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handle), base_url=get_settings().ocr_url
    )
    return OcrClient(settings=get_settings(), http_client=fake_http)


@pytest.fixture
async def client(
    apertus: FakeApertus, searxng_client: SearxngClient
) -> AsyncIterator[httpx2.AsyncClient]:
    """API client with the customer's token; Apertus, the bank, OCR and SearXNG are faked."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if GUARDRAIL_SCHEMA in request.content.decode():
            apertus.guardrail_requests.append(body)
            if apertus.status != 200:
                return httpx2.Response(apertus.status, json={"error": {"message": "fake failure"}})
            check = apertus.guardrails.pop(0) if apertus.guardrails else OK_GUARDRAIL
            return _fake_completion(body=body, content=check)
        apertus.requests.append(body)
        if apertus.status != 200:
            return httpx2.Response(apertus.status, json={"error": {"message": "fake failure"}})
        # Only `structured` sets a temperature, which marks a tool decision request.
        if "temperature" not in body:
            return _fake_completion(body=body, content=apertus.reply)
        if apertus.structured_reply is not None:
            return _fake_completion(body=body, content=apertus.structured_reply(body))
        decision = apertus.decisions.pop(0) if apertus.decisions else NO_TOOL_DECISION
        return _fake_completion(body=body, content=decision)

    fake_http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    app.state.apertus = ApertusClient(settings=get_settings(), http_client=fake_http)
    app.state.banking = fake_banking_client()
    app.state.ocr = fake_ocr_client()
    app.state.searxng = searxng_client
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {CUSTOMER_TOKEN}"},
    ) as api:
        yield api
    await app.state.apertus.close()
    await app.state.banking.close()
    await app.state.ocr.close()
    await searxng_client.close()
