import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient, LLMResult, LLMStream, Message, Model
from app.core.errors import BadRequestError
from app.core.streaming import ToolCallEvent, ToolResultEvent
from app.core.tools import Tool, Turn
from app.features.tool_calls import service as tool_call_service
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.schemas import (
    RequestToolCallConfirmationCreate,
    ToolDecision,
    ToolRequest,
)
from app.features.tool_calls.service import (
    TOOL_FAILED,
    BoardStyle,
    Paragraphs,
    SwissFigures,
    SwissSpelling,
    ToolCallService,
    board_style,
    swiss_figures,
    swiss_text,
    without_empty_end,
)
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

    def stream_chat(self, messages: list[Message], *, model: Model, purpose: str) -> LLMStream:
        self.prompts.append(messages)

        async def chunks() -> AsyncIterator[str]:
            yield self.answer

        stream = LLMStream(chunks=chunks())
        stream.result = LLMResult(
            content=self.answer, model="fake", latency_ms=1, tokens_in=None, tokens_out=None
        )
        return stream


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


class CollectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Collected(BaseModel):
    count: int


async def _collect(args: CollectArgs, turn: Turn) -> Collected:
    if len(turn.results) == 0:
        raise BadRequestError("Nothing to collect yet.")
    return Collected(count=len(turn.results))


# Builds on the turn's results, as build_widget does.
COLLECT = Tool(
    name="collect",
    title="Collect",
    icon="search",
    description="Counts the turn's results.",
    args_schema=CollectArgs,
    turn_handler=_collect,
)


async def _errors(session: AsyncSession, decisions: list[ToolDecision]) -> list[str | None]:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=cast(ApertusClient, RecordingApertus(decisions=decisions)),
        tools=[LOOKUP, COLLECT],
        today=TODAY,
        confirmations=Confirmations(),
    )
    await service.create_answer(
        conversation_id=conversation.id, message_id=message.id, messages=CHAT
    )
    calls = await service.list_tool_calls(conversation_id=conversation.id)
    return [call.error for call in calls]


def _lookup_and_collect(query: str) -> ToolDecision:
    collect = ToolRequest(reason="Because.", tool="collect", arguments={})
    return ToolDecision(plan="Look up, collect.", calls=[*_lookups(query).calls, collect])


async def test_a_tool_that_builds_on_the_turn_runs_again_once_the_figures_are_there(
    session: AsyncSession,
) -> None:
    decisions = [_lookup_and_collect("missing"), _lookup_and_collect("Zurich")]

    errors = await _errors(session=session, decisions=decisions)

    assert errors == [
        "No page for 'missing'. Send a town instead.",
        "Nothing to collect yet.",
        None,
        None,
    ]


async def test_an_unknown_argument_is_named_as_one_to_leave_out(session: AsyncSession) -> None:
    extra = ToolRequest(reason="Because.", tool="collect", arguments={"group_by": "month"})

    errors = await _errors(
        session=session, decisions=[ToolDecision(plan="Collect.", calls=[extra])]
    )

    assert errors == [
        "Invalid arguments. group_by: This tool has no such argument. "
        "Send the call again without it"
    ]


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


async def test_arguments_of_a_call_that_is_not_editable_cannot_be_changed(
    session: AsyncSession,
) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    confirmations = Confirmations()
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=cast(ApertusClient, RecordingApertus(decisions=[_lookups("Bern")])),
        tools=[replace(LOOKUP, confirmation="This looks it up.")],
        today=TODAY,
        confirmations=confirmations,
    )

    async def answer() -> None:
        while not confirmations.waiting:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
        ((_, tool_call_id),) = confirmations.waiting
        edited = RequestToolCallConfirmationCreate(is_allowed=True, arguments={"query": "Chur"})
        with pytest.raises(BadRequestError, match="cannot be changed"):
            service.confirm_tool_call(
                conversation_id=conversation.id, tool_call_id=tool_call_id, data=edited
            )
        service.confirm_tool_call(
            conversation_id=conversation.id,
            tool_call_id=tool_call_id,
            data=RequestToolCallConfirmationCreate(is_allowed=True),
        )

    async def stream() -> list[bool]:
        editable = []
        events = service.stream_answer(
            conversation_id=conversation.id, message_id=message.id, messages=CHAT
        )
        async for event in events:
            if isinstance(event, ToolCallEvent):
                editable.append(event.is_editable)
            # The fake has no stream for the answer, so the turn ends with the call.
            if isinstance(event, ToolResultEvent):
                break
        return editable

    async with asyncio.timeout(5):
        editable, _ = await asyncio.gather(stream(), answer())

    assert editable == [False]
    (call,) = await service.list_tool_calls(conversation_id=conversation.id)
    assert (call.arguments, call.error) == ({"query": "Bern"}, None)


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


@pytest.mark.parametrize(
    ("text", "swiss"),
    [
        ("CHF 1 050.00", "CHF 1'050.00"),
        ("CHF 1 050.00 and CHF 1 174.96", "CHF 1'050.00 and CHF 1'174.96"),
        ("CHF 12,000.50 left", "CHF 12'000.50 left"),
        ("1 234 567.80 CHF", "1'234'567.80 CHF"),
        ("CHF 1 050", "CHF 1'050"),
        ("CHF 2’950.20", "CHF 2'950.20"),
        ("on 23 December 2026, CHF 124.96", "on 23 December 2026, CHF 124.96"),
        ("IBAN CH93 0076 2011 6238 5295 7", "IBAN CH93 0076 2011 6238 5295 7"),
        ("call 079 123 45 67", "call 079 123 45 67"),
        ("in 2026 120 bookings", "in 2026 120 bookings"),
        ("on 23.12. and 1,5 %", "on 23.12. and 1,5 %"),
    ],
)
def test_swiss_figures_write_thousands_with_an_apostrophe(text: str, swiss: str) -> None:
    assert swiss_figures(text=text) == swiss


def test_swiss_figures_carry_a_number_across_pieces() -> None:
    figures = SwissFigures()
    pieces = ["You have CHF 1", " 0", "50.00 left on 23", " December 2026 and CHF 1 ", "174.96"]

    streamed = "".join(figures.feed(text=piece) for piece in pieces) + figures.flush()

    assert streamed == "You have CHF 1'050.00 left on 23 December 2026 and CHF 1'174.96"


def test_paragraphs_beside_a_board_get_an_empty_line() -> None:
    paragraphs = Paragraphs(is_on=True)
    pieces = ["\n\nYes, but only just.  \n", "With it, CHF 1'174.96.\nItems:\n- one\n- two"]

    text = "".join(paragraphs.feed(text=piece) for piece in pieces)

    assert text == "Yes, but only just.  \n\nWith it, CHF 1'174.96.\n\nItems:\n- one\n- two"


def test_a_streamed_answer_beside_a_board_reads_as_the_stored_one() -> None:
    text = "Yes, but only just.\nCHF 1 050.00 are missing. Straße\n- one\n- two\nEnd."
    spelling, numbers, paragraphs = SwissSpelling(), SwissFigures(), Paragraphs(is_on=True)

    streamed = "".join(
        paragraphs.feed(text=numbers.feed(text=spelling.feed(text=char))) for char in text
    ) + paragraphs.feed(text=numbers.flush())

    assert streamed == Paragraphs(is_on=True).feed(text=swiss_text(text=text))


def test_beside_a_board_a_day_of_this_year_drops_its_year_and_dashes_become_commas() -> None:
    style = BoardStyle(year=2026)
    pieces = [
        "Left on 23.12.2026 —",
        " that is CHF 4.63, from 01.01.–27.11.",
        " and 05.01.2027, on 23 Dec",
        "ember 2026 and 24 December, not 5 January 2027, on 23. 12. 2026.",
    ]

    text = "".join(style.feed(text=piece) for piece in pieces) + style.flush()

    assert text == (
        "Left on 23.12., that is CHF 4.63, from 01.01.–27.11. and 05.01.2027, on 23.12. and"
        " 24.12., not 5 January 2027, on 23.12."
    )


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        (
            "It cannot wait. The last is Assura on 23.12. No figure is referenced here.",
            "It cannot wait. The last is Assura on 23.12.",
        ),
        (
            "It cannot wait. The last is Assura on 23.12. Only a payee can agree to a later date.",
            "It cannot wait. The last is Assura on 23.12. Only a payee can agree to a later date.",
        ),
        ("Yes, but only just.\n\nThat is all.", "Yes, but only just.\n\nThat is all."),
        (
            "I made a board for it. It starts with CHF 5.00.\n\nTell me what it may cost.",
            "I made a board for it. It starts with CHF 5.00.\n\nTell me what it may cost.",
        ),
        ("Yes. CHF 5.00 are left.\n\nThis is reassuring overall.", "Yes. CHF 5.00 are left."),
    ],
)
def test_an_answer_beside_a_board_does_not_end_on_an_empty_sentence(text: str, kept: str) -> None:
    assert without_empty_end(text=text) == kept


@pytest.mark.parametrize(
    ("text", "styled"),
    [
        (
            "It is due in three days; according to the tile's description, it cannot wait.",
            "It is due in three days; it cannot wait.",
        ),
        (
            'You find it in the "Groceries in November" tile on your board.',
            'You find it in "Groceries in November" on your board.',
        ),
        (
            'Your new "Subscriptions" tile shows two payments.',
            'Your new "Subscriptions" shows two payments.',
        ),
    ],
)
def test_beside_a_board_the_safe_cases_of_tile_are_rewritten(text: str, styled: str) -> None:
    assert board_style(text=text, year=2026) == styled
