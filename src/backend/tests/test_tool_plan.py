import json
from typing import Any

import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient
from app.core.config import get_settings
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.service import ToolCallService
from tests.conftest import TODAY, _fake_completion
from tests.factories import make_conversation, make_message
from tests.lookup_tool import LOOKUP

THINKING_MODEL = "fake-thinking"
PLAN = "Call lookup with query Zurich, the user asks about Zurich."
DECISION = '{"plan": "Look up Zurich.", "calls": [{"tool": "lookup", "arguments": {}}]}'


async def _turn(
    session: AsyncSession, thinking: str | None, plan_reply: str
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """One turn; returns the answer, every request the gateway got, and the stored calls' tools."""
    requests: list[dict[str, Any]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        requests.append(body)
        if body["model"] == THINKING_MODEL:
            return _fake_completion(body=body, content=plan_reply)
        if "temperature" in body:
            return _fake_completion(
                body=body, content=DECISION if len(requests) <= 2 else '{"plan": "Done."}'
            )
        return _fake_completion(body=body, content="Zurich it is.")

    settings = get_settings().model_copy(update={"llm_name_thinking": thinking})
    apertus = ApertusClient(
        settings=settings, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    )
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=apertus,
        tools=[LOOKUP],
        today=TODAY,
        confirmations=Confirmations(),
    )
    content, _ = await service.create_answer(
        conversation_id=conversation.id,
        message_id=message.id,
        messages=[
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Tell me about Zurich."},
        ],
    )
    calls = await service.list_tool_calls(conversation_id=conversation.id)
    return content, requests, [call.tool_name for call in calls]


def _system(request: dict[str, Any]) -> str:
    return request["messages"][0]["content"]


async def test_without_a_thinking_model_no_plan_is_asked_for(session: AsyncSession) -> None:
    content, requests, tools = await _turn(session=session, thinking=None, plan_reply=PLAN)

    assert content == "Zurich it is."
    assert tools == ["lookup"]
    assert [request["model"] for request in requests] == ["fake-smart"] * 3
    assert "A planner" not in _system(request=requests[0])


async def test_the_decision_gets_the_plan_without_the_reasoning(session: AsyncSession) -> None:
    reply = f"<|inner_prefix|>Hmm, Zurich. Maybe weather?<|inner_suffix|>\n{PLAN}"

    content, requests, tools = await _turn(
        session=session, thinking=THINKING_MODEL, plan_reply=reply
    )

    assert content == "Zurich it is."
    assert tools == ["lookup"]
    assert [request["model"] for request in requests] == [THINKING_MODEL] + ["fake-smart"] * 3
    assert "temperature" not in requests[0]
    # A system message would switch the reasoning off.
    plan_request = requests[0]["messages"]
    assert [message["role"] for message in plan_request] == ["user"]
    assert plan_request[0]["content"].endswith("Tell me about Zurich.")
    assert "lookup" in plan_request[0]["content"]
    decision = _system(request=requests[1])
    assert PLAN in decision
    assert "Maybe weather" not in decision
    # Later rounds ask the thinking model nothing more.
    assert PLAN in _system(request=requests[2])


async def test_a_plan_cut_off_while_thinking_still_answers(session: AsyncSession) -> None:
    content, requests, tools = await _turn(
        session=session, thinking=THINKING_MODEL, plan_reply="<|inner_prefix|>Hmm, Zur"
    )

    assert content == "Zurich it is."
    assert tools == ["lookup"]
    assert "A planner" not in _system(request=requests[1])
    assert "Hmm" not in _system(request=requests[1])
