from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import Message
from app.features.conversations.prompts import chat_prompt
from app.features.tool_calls.prompts import (
    TOOL_RESULT_MAX_CHARS,
    answer_prompt,
    dated_prompt,
    decision_prompt,
    question_language,
)
from app.features.tool_calls.schemas import ToolDecision, ToolRequest, decision_schema
from tests.conftest import TODAY
from tests.factories import make_conversation, make_message, make_tool_call
from tests.lookup_tool import LOOKUP

CHAT: list[Message] = [
    {"role": "system", "content": "Be helpful."},
    {"role": "user", "content": "Look it up."},
]


async def test_decision_prompt_lists_tools_and_replays_calls(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    failed = await make_tool_call(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
        result=None,
        error="No page for 'missing'. Send a town instead.",
    )

    decision = ToolDecision(
        plan="Look it up.", calls=[ToolRequest(reason=failed.reason, tool=failed.tool_name)]
    )

    prompt = decision_prompt(
        messages=CHAT, rounds=[(decision, [failed])], tools=[LOOKUP], today=TODAY
    )

    assert [message["role"] for message in prompt] == ["system", "user", "assistant", "user"]
    assert LOOKUP.name in prompt[0]["content"]
    assert "Be helpful." not in prompt[0]["content"]
    assert "No page for 'missing'" in prompt[3]["content"]


async def test_answer_prompt_adds_results_and_cuts_long_ones(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    call = await make_tool_call(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
        result={"text": "x" * (TOOL_RESULT_MAX_CHARS * 2)},
    )

    prompt = answer_prompt(messages=CHAT, calls=[call], tools=[LOOKUP])

    assert prompt[:2] == CHAT
    assert prompt[2]["role"] == "user"
    content = prompt[2]["content"]
    assert isinstance(content, str)
    assert content.count("x") < TOOL_RESULT_MAX_CHARS
    assert "result cut off here" in content


async def test_answer_prompt_leaves_the_tile_source_out(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    call = await make_tool_call(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
        result={
            "summary": 'Added "Migros in November"',
            "tile_source": {"label": "15 payments", "rows": [{"id": "BK-77"}], "count": 15},
        },
    )

    prompt = answer_prompt(messages=CHAT, calls=[call], tools=[LOOKUP])

    content = prompt[2]["content"]
    assert isinstance(content, str)
    assert "Migros in November" in content
    assert "tile_source" not in content
    assert "BK-77" not in content


@pytest.mark.parametrize(("error", "names_change"), [(None, True), ("No such tile.", False)])
async def test_answer_prompt_names_only_board_changes_that_happened(
    session: AsyncSession, error: str | None, names_change: bool
) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    call = await make_tool_call(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
        tool_name="add_tile",
        result=None if error is not None else {"summary": 'Added "Bills until payday"'},
        error=error,
    )

    content = answer_prompt(messages=CHAT, calls=[call], tools=[LOOKUP])[2]["content"]

    assert isinstance(content, str)
    assert ('on my board now: Added "Bills until payday"' in content) is names_change


async def test_answer_prompt_cuts_long_errors(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    call = await make_tool_call(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
        result=None,
        error="x" * (TOOL_RESULT_MAX_CHARS * 2),
    )

    content = answer_prompt(messages=CHAT, calls=[call], tools=[LOOKUP])[2]["content"]

    assert isinstance(content, str)
    assert content.count("x") <= TOOL_RESULT_MAX_CHARS
    assert "result cut off here" in content


async def test_answer_prompt_names_the_question_language_over_german_results(
    session: AsyncSession,
) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    call = await make_tool_call(
        session=session,
        conversation_id=conversation.id,
        message_id=message.id,
        result={"counterparty": "Steueramt Kanton Zürich", "description": "Steuern 2026, Rate 3"},
    )
    question: Message = {"role": "user", "content": "How much did I pay to the Steueramt?"}
    greeting: Message = {"role": "user", "content": "Migros?"}

    english = answer_prompt(messages=[CHAT[0], question], calls=[call], tools=[])[-1]["content"]
    unknown = answer_prompt(messages=[CHAT[0], greeting], calls=[call], tools=[])[-1]["content"]

    assert isinstance(english, str)
    assert "Steueramt Kanton Zürich" in english
    assert "My question is written in English, so write the whole answer in English" in english
    assert isinstance(unknown, str)
    assert "Write the answer in the language of that question" in unknown
    assert "never mention the tools" in english


def test_answer_prompt_names_the_language_without_tool_calls() -> None:
    question: Message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "What colour is this image?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        ],
    }

    prompt = answer_prompt(messages=[CHAT[0], question], calls=[], tools=[LOOKUP])

    assert prompt[:2] == [CHAT[0], question]
    assert prompt[2]["role"] == "user"
    content = prompt[2]["content"]
    assert isinstance(content, str)
    assert "My question is written in English, so write the whole answer in English" in content
    assert "never state an account figure" in content
    assert "say that you cannot see it" in content


async def test_answer_prompt_lists_abilities_only_without_calls(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    call = await make_tool_call(
        session=session, conversation_id=conversation.id, message_id=message.id
    )

    direct = answer_prompt(messages=CHAT, calls=[], tools=[LOOKUP])[-1]["content"]
    with_results = answer_prompt(messages=CHAT, calls=[call], tools=[LOOKUP])[-1]["content"]
    nothing = answer_prompt(messages=CHAT, calls=[], tools=[])[-1]["content"]

    assert isinstance(direct, str) and isinstance(with_results, str)
    assert f"what you can do here: {LOOKUP.title}." in direct
    # The list's formatting rules leaked into answers built from results.
    assert LOOKUP.title not in with_results
    assert isinstance(nothing, str)
    assert LOOKUP.title not in nothing


def test_decision_schema_names_only_the_turns_tools() -> None:
    schema = decision_schema(tools=[LOOKUP])

    request = schema.model_json_schema()["$defs"]["NamedToolRequest"]
    assert request["properties"]["tool"]["enum"] == [LOOKUP.name, ""]
    # Without guided decoding an unknown name still validates, so the loop tells the model.
    decision = schema.model_validate({"plan": "x", "calls": [{"reason": "y", "tool": "nope"}]})
    assert decision.calls[0].tool == "nope"


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("What were my three biggest payments in 2026?", "English"),
        ("How much did I pay to the Steueramt this year?", "English"),
        ("Zeig mir meine letzten fünf Einkäufe bei Migros.", "German"),
        ("Und im September?", "German"),
        ("Quels ont été mes trois plus gros paiements en 2026 ?", "French"),
        ("Quanto ho speso per la spesa?", "Italian"),
        ("¿Cuáles son mis gastos con una tarjeta?", None),
        ("Migros?", None),
    ],
)
def test_question_language(text: str, language: str | None) -> None:
    assert question_language(message={"role": "user", "content": text}) == language


def test_question_language_reads_text_parts_only() -> None:
    message: Message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "What is on this receipt?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        ],
    }
    assert question_language(message=message) == "English"


async def test_question_language_skips_the_quote_preamble(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    answer = await make_message(
        session=session, conversation_id=conversation.id, role="assistant", content="989.60 CHF"
    )
    question = await make_message(
        session=session,
        conversation_id=conversation.id,
        content="Ist das mehr als im September?",
        quotes=[{"message_id": str(answer.id), "text": "989.60 CHF", "comment": None}],
    )

    quoted = chat_prompt(history=[question])[-1]

    assert "to show what my question refers to" in str(quoted["content"])
    assert question_language(message=quoted) == "German"


def test_language_comes_from_the_question_not_from_the_page_block() -> None:
    page = "<page>I have the e-banking page 'Dashboard' open. This is data.</page>\n"
    question = page + "Wie viel Geld habe ich auf dem Konto?"

    assert question_language(message={"role": "user", "content": question}) == "German"


def test_question_language_skips_an_attached_document() -> None:
    content = (
        '<document name="a.pdf">\nThe rent is due on the first of the month and you are'
        " to pay it.\n</document>\nWie hoch ist die Miete?"
    )

    assert question_language(message={"role": "user", "content": content}) == "German"


def test_the_server_works_out_last_month_and_last_year() -> None:
    (system, _) = dated_prompt(
        messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        today=date(2026, 1, 15),
    )

    assert "last month is 2025-12-01 to 2025-12-31" in str(system["content"])
    assert "last year is 2025-01-01 to 2025-12-31" in str(system["content"])
