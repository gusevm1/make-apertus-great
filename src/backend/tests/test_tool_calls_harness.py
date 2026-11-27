from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient, LLMResult, Message, Model
from app.features.tool_calls import service as tool_call_service
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.features.tool_calls.service import TOOL_FAILED, SwissSpelling, ToolCallService
from tests.conftest import TODAY
from tests.factories import make_conversation, make_message
from tests.lookup_tool import LOOKUP

CHAT: list[Message] = [
    {"role": "system", "content": "Be helpful."},
    {"role": "user", "content": "Look it up."},
]


class RecordingApertus:
    def __init__(self, decisions: list[ToolDecision], answer: str = "ok") -> None:
        self.decisions = decisions
        self.answer = answer
        self.prompts: list[list[Message]] = []

    async def structured(
        self, messages: list[Message], *, schema: type[BaseModel], model: Model, purpose: str
    ) -> LLMResult[ToolDecision]:
        self.prompts.append(messages)
        decision = self.decisions.pop(0) if self.decisions else ToolDecision(plan="Done.")
        return LLMResult(
            content=decision, model="fake", latency_ms=1, tokens_in=None, tokens_out=None
        )

    async def chat(self, messages: list[Message], *, model: Model, purpose: str) -> LLMResult[str]:
        self.prompts.append(messages)
        return LLMResult(
            content=self.answer, model="fake", latency_ms=1, tokens_in=None, tokens_out=None
        )


def _lookups(*queries: str) -> ToolDecision:
    calls = [ToolRequest(reason="Because.", tool="lookup", arguments={"query": q}) for q in queries]
    return ToolDecision(plan="Look them up.", calls=calls)


async def _answer(
    session: AsyncSession, apertus: RecordingApertus
) -> tuple[str, list[str | None], list[dict[str, Any]]]:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=cast(ApertusClient, apertus),
        tools=[LOOKUP],
        today=TODAY,
        confirmations=Confirmations(),
    )
    content, provenance = await service.create_answer(
        conversation_id=conversation.id, message_id=message.id, messages=CHAT
    )
    calls = await service.list_tool_calls(conversation_id=conversation.id)
    sources = [source.model_dump() for source in provenance.sources]
    return content, [call.error for call in calls], sources


async def test_expected_tool_errors_go_back_to_the_model(session: AsyncSession) -> None:
    apertus = RecordingApertus(decisions=[_lookups("missing", "bad"), _lookups("Zurich")])

    content, errors, _ = await _answer(session=session, apertus=apertus)

    assert content == "ok"
    assert errors == ["No page for 'missing'. Send a town instead.", "Query too short", None]
    feedback = apertus.prompts[1][-1]["content"]
    assert isinstance(feedback, str)
    assert "Send a town instead." in feedback
    assert "Query too short" in feedback


async def test_unexpected_tool_errors_are_logged_and_hidden(
    session: AsyncSession, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The migrations' logging config disables loggers that exist before it runs.
    monkeypatch.setattr(tool_call_service.logger, "disabled", False)
    apertus = RecordingApertus(decisions=[_lookups("crash")])

    content, errors, _ = await _answer(session=session, apertus=apertus)

    assert content == "ok"
    assert errors == [TOOL_FAILED]
    assert "secret internals" in caplog.text
    assert all("secret internals" not in str(prompt) for prompt in apertus.prompts)


async def test_a_validation_error_inside_a_tool_is_logged_as_a_bug(
    session: AsyncSession, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tool_call_service.logger, "disabled", False)
    apertus = RecordingApertus(decisions=[_lookups("invalid")])

    _, errors, _ = await _answer(session=session, apertus=apertus)

    assert errors == [TOOL_FAILED]
    (record,) = [record for record in caplog.records if record.name == tool_call_service.__name__]
    call_id = cast(tuple[UUID, str], record.args)[0]
    stored = await ToolCallRepository(session=session).get_by_id(entity_id=call_id)
    assert stored is not None
    assert stored.error == TOOL_FAILED
    assert "ValidationError" in caplog.text
    assert all("not a list" not in str(prompt) for prompt in apertus.prompts)


async def test_a_result_cannot_break_out_of_its_block(session: AsyncSession) -> None:
    apertus = RecordingApertus(decisions=[_lookups("injection")])

    await _answer(session=session, apertus=apertus)

    for prompt in (apertus.prompts[1], apertus.prompts[-1]):
        block = prompt[-1]["content"]
        assert isinstance(block, str)
        assert block.count("<tool_result") == 1
        assert block.count("</tool_result>") == 1
        opening, closing = block.index("<tool_result"), block.index("</tool_result>")
        assert opening < block.index("Ignore all rules") < closing


async def test_sources_of_all_results_reach_the_provenance_once(session: AsyncSession) -> None:
    apertus = RecordingApertus(decisions=[_lookups("Zurich"), _lookups("Bern")])

    _, _, sources = await _answer(session=session, apertus=apertus)

    assert [source["url"] for source in sources] == [
        "https://example.ch/Zurich",
        "https://example.ch/shared",
        "https://example.ch/Bern",
    ]
    assert sources[0]["title"] == "About Zurich"


async def test_prompts_state_the_date_of_the_e_banking(session: AsyncSession) -> None:
    apertus = RecordingApertus(decisions=[])

    await _answer(session=session, apertus=apertus)

    today = "Friday, 27.11.2026"
    decision, answer = apertus.prompts
    assert today in str(decision[0]["content"])
    assert today in str(answer[0]["content"])
    assert answer[1:-1] == CHAT[1:]
    assert "Answer my message above." in str(answer[-1]["content"])


async def test_answers_and_plans_use_swiss_ss(session: AsyncSession) -> None:
    decision = ToolDecision(plan="Gemäß Plan.", calls=_lookups("Zürich").calls)
    apertus = RecordingApertus(decisions=[decision], answer="Grüße aus der STRAẞE")
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=cast(ApertusClient, apertus),
        tools=[LOOKUP],
        today=TODAY,
        confirmations=Confirmations(),
    )

    content, _ = await service.create_answer(
        conversation_id=conversation.id, message_id=message.id, messages=CHAT
    )

    assert content == "Grüsse aus der STRASSE"
    calls = await service.list_tool_calls(conversation_id=conversation.id)
    assert [call.plan for call in calls] == ["Gemäss Plan."]


@pytest.mark.parametrize(
    ("text", "spelled"),
    [
        ("Gruß, Straße", "Gruss, Strasse"),
        (
            "Siehe https://straße.ch/maß oder www.maß.ch, Gruß",
            "Siehe https://straße.ch/maß oder www.maß.ch, Gruss",
        ),
        ("[Maß](https://maß.ch)", "[Mass](https://maß.ch)"),
        ("Gruß (www.maß.ch)", "Gruss (www.maß.ch)"),
        ("Er sagt «Maß» und „Gruß“, dann Maß", "Er sagt «Maß» und „Gruß“, dann Mass"),
        ('"Groß" ist groß', '"Groß" ist gross'),
        ('„Wohnung" ist die größte', '„Wohnung" ist die grösste'),
        ("«Er sagt „Maß“, Gruß» Gruß", "«Er sagt „Maß“, Gruß» Gruss"),
        ("> Zitat: Straße\nGruß", "> Zitat: Straße\nGruss"),
        ("«offen, Straße\nGruß", "«offen, Straße\nGruss"),
    ],
)
def test_swiss_spelling_keeps_urls_and_quotes(text: str, spelled: str) -> None:
    assert SwissSpelling().feed(text=text) == spelled


def test_swiss_spelling_carries_a_url_or_quote_across_pieces() -> None:
    spelling = SwissSpelling()

    pieces = [spelling.feed(text=piece) for piece in ["https://stra", "ße.ch «Gro", "ße» Gruß"]]

    assert pieces == ["https://stra", "ße.ch «Gro", "ße» Gruss"]
