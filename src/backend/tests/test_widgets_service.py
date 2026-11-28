from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import httpx2
import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.apertus import ApertusClient, LLMResult, LLMStream, Message, Model
from app.core.errors import BadRequestError, UpstreamError
from app.core.tools import Tool, TurnResult
from app.features.figure_checks.service import FigureCheckService
from app.features.ledger.service import LedgerService
from app.features.payments.service import PaymentService
from app.features.tool_calls.confirmations import Confirmations
from app.features.tool_calls.repository import ToolCallRepository
from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from app.features.tool_calls.service import ToolCallService
from app.features.widgets import tools as widget_tools
from app.features.widgets.catalogue.render import _named, render
from app.features.widgets.catalogue.schemas import WidgetSpec
from app.features.widgets.repository import WidgetRepository, WidgetVersionRepository
from app.features.widgets.schemas import BuildWidgetArgs
from app.features.widgets.service import WidgetService, widget_data
from tests.conftest import TODAY, fake_banking_client
from tests.factories import DEMO_USER_ID, make_conversation, make_message

CHAT: list[Message] = [
    {"role": "system", "content": "Be helpful."},
    {"role": "user", "content": "Show my spending per month as a chart."},
]
GOOD_SPEC = {
    "title": "Spending per month",
    "body": {"type": "bar_chart", "data": "months", "x": "month", "y": "money_out_chf"},
}
BAD_SPEC = {
    "title": "Spending per month",
    "body": {"type": "bar_chart", "data": "monthz", "x": "month", "y": "money_out_chf"},
}
MONTHS_RESULT = {
    "months": [
        {"month": "2026-09", "money_out_chf": "17273.60"},
        {"month": "2026-10", "money_out_chf": "10598.77"},
    ],
    "row_ids": {"2026-09": ["BK-01", "BK-02"], "2026-10": ["BK-03"]},
}


class ScriptedApertus:
    """Answers tool decisions and widget specs from two scripts; an exception fails the call."""

    has_thinking_model = False

    def __init__(
        self, decisions: list[ToolDecision], specs: list[dict[str, Any] | Exception]
    ) -> None:
        self.decisions = decisions
        self.specs = specs
        self.spec_prompts: list[list[Message]] = []

    async def structured(
        self, messages: list[Message], *, schema: type[BaseModel], model: Model, purpose: str
    ) -> LLMResult[Any]:
        if schema is WidgetSpec:
            self.spec_prompts.append(messages)
            spec = self.specs.pop(0)
            if isinstance(spec, Exception):
                raise spec
            content: BaseModel = WidgetSpec.model_validate(spec)
        else:
            content = self.decisions.pop(0) if self.decisions else ToolDecision(plan="Done.")
        return LLMResult(
            content=content, model="fake", latency_ms=1, tokens_in=None, tokens_out=None
        )

    def stream_chat(self, messages: list[Message], *, model: Model, purpose: str) -> LLMStream:
        async def chunks() -> AsyncIterator[str]:
            yield "ok"

        stream = LLMStream(chunks=chunks())
        stream.result = LLMResult(
            content="ok", model="fake", latency_ms=1, tokens_in=None, tokens_out=None
        )
        return stream


class MonthsArgs(BaseModel):
    pass


class MonthsResult(BaseModel):
    months: list[dict[str, Any]]
    row_ids: dict[str, list[str]]


async def _months(args: MonthsArgs) -> MonthsResult:
    months = [{"month": "2026-09", "money_out_chf": Decimal("17273.60")}]
    return MonthsResult(months=months, row_ids={"2026-09": ["BK-01", "BK-02"]})


MONTHS = Tool(
    name="sum_by_month",
    title="Add up your months",
    icon="bar-chart-3",
    description="Sums per month.",
    args_schema=MonthsArgs,
    handler=_months,
)


class PaymentsResult(BaseModel):
    items: list[dict[str, Any]]


async def _payments(args: MonthsArgs) -> PaymentsResult:
    return PaymentsResult(items=[{"id": "SO-1", "payee": "Landlord", "amount_chf": "1850.00"}])


PAYMENTS = Tool(
    name="list_upcoming_payments",
    title="List upcoming payments",
    icon="calendar",
    description="Payments due soon.",
    args_schema=MonthsArgs,
    handler=_payments,
)


def _service(session: AsyncSession, apertus: ScriptedApertus) -> WidgetService:
    banking = fake_banking_client()
    ledger = LedgerService(banking=banking)
    return WidgetService(
        widgets=WidgetRepository(session=session),
        versions=WidgetVersionRepository(session=session),
        apertus=cast(ApertusClient, apertus),
        figure_checks=FigureCheckService(),
        ledger=ledger,
        payments=PaymentService(banking=banking, ledger=ledger),
    )


def _results() -> list[TurnResult]:
    return [TurnResult(tool_call_id=uuid4(), tool_name="sum_by_month", result=MONTHS_RESULT)]


def _args() -> BuildWidgetArgs:
    return BuildWidgetArgs(title="Spending", request="Show my spending per month as a chart.")


def _call(tool: str, **arguments: Any) -> ToolDecision:
    request = ToolRequest(reason="Because.", tool=tool, arguments=arguments)
    return ToolDecision(plan="Fetch, then draw.", calls=[request])


async def test_a_turn_draws_and_keeps_a_widget_from_its_earlier_results(
    session: AsyncSession,
) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    decisions = [
        _call("sum_by_month"),
        _call("build_widget", title="Spending", request="Spending per month as a chart"),
    ]
    apertus = ScriptedApertus(decisions=decisions, specs=[GOOD_SPEC])
    widgets = _service(session=session, apertus=apertus)
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=cast(ApertusClient, apertus),
        tools=[MONTHS, *widget_tools.get_tools(service=widgets, owner_id=DEMO_USER_ID)],
        today=TODAY,
        confirmations=Confirmations(),
    )

    await service.create_answer(
        conversation_id=conversation.id, message_id=message.id, messages=CHAT
    )

    fetch, build = await service.list_tool_calls(conversation_id=conversation.id)
    assert build.error is None
    assert build.result is not None
    widget = await widgets.get_widget(widget_id=build.result["widget_id"], owner_id=DEMO_USER_ID)
    version, html = await widgets.render_version(widget=widget, version_number=1, form="static")
    assert widget.conversation_id == conversation.id
    assert version.spec == GOOD_SPEC
    assert version.data["months"] == [
        {"month": "2026-09", "money_out_chf": 17273.6, "booking_ids": ["BK-01", "BK-02"]}
    ]
    assert version.tool_call_ids == [str(fetch.id)]
    assert version.checks[0].detail == "first try"
    assert "17&#39;274" in html or "17'274" in html


async def test_a_widget_listed_before_a_fetch_still_draws_that_fetch(
    session: AsyncSession,
) -> None:
    conversation = await make_conversation(session=session)
    message = await make_message(session=session, conversation_id=conversation.id)
    calls = [
        ToolRequest(reason="Months.", tool="sum_by_month", arguments={}),
        ToolRequest(
            reason="Draw.",
            tool="build_widget",
            arguments={"title": "Spending", "request": "Spending and payments as a chart"},
        ),
        ToolRequest(reason="Payments.", tool="list_upcoming_payments", arguments={}),
    ]
    apertus = ScriptedApertus(
        decisions=[ToolDecision(plan="Fetch, then draw.", calls=calls)], specs=[GOOD_SPEC]
    )
    widgets = _service(session=session, apertus=apertus)
    service = ToolCallService(
        tool_calls=ToolCallRepository(session=session),
        apertus=cast(ApertusClient, apertus),
        tools=[MONTHS, PAYMENTS, *widget_tools.get_tools(service=widgets, owner_id=DEMO_USER_ID)],
        today=TODAY,
        confirmations=Confirmations(),
    )

    await service.create_answer(
        conversation_id=conversation.id, message_id=message.id, messages=CHAT
    )

    *fetches, build = await service.list_tool_calls(conversation_id=conversation.id)
    assert build.tool_name == "build_widget"
    assert build.result is not None
    widget = await widgets.get_widget(widget_id=build.result["widget_id"], owner_id=DEMO_USER_ID)
    version, _ = await widgets.render_version(widget=widget, version_number=1, form="live")
    assert version.data["upcoming_payments"][0]["payee"] == "Landlord"
    assert version.tool_call_ids == [str(fetch.id) for fetch in fetches]


async def test_a_path_that_does_not_resolve_goes_back_to_apertus_once(
    session: AsyncSession,
) -> None:
    conversation = await make_conversation(session=session)
    apertus = ScriptedApertus(decisions=[], specs=[BAD_SPEC, GOOD_SPEC])
    widgets = _service(session=session, apertus=apertus)

    built = await widgets.build_widget(
        owner_id=DEMO_USER_ID, conversation_id=conversation.id, args=_args(), results=_results()
    )

    version, _ = await widgets.render_version(
        widget=await widgets.get_widget(widget_id=built.widget_id, owner_id=DEMO_USER_ID),
        version_number=1,
        form="live",
    )
    assert version.spec == GOOD_SPEC
    assert version.checks[0].detail == "after one repair"
    repair = apertus.spec_prompts[1][-1]["content"]
    assert isinstance(repair, str)
    assert "monthz" in repair


@pytest.mark.parametrize(
    "second", [BAD_SPEC, UpstreamError("Model returned invalid WidgetSpec twice")]
)
async def test_a_second_failure_keeps_a_plain_widget(
    session: AsyncSession, second: dict[str, Any] | Exception
) -> None:
    conversation = await make_conversation(session=session)
    apertus = ScriptedApertus(decisions=[], specs=[BAD_SPEC, second])
    widgets = _service(session=session, apertus=apertus)

    built = await widgets.build_widget(
        owner_id=DEMO_USER_ID, conversation_id=conversation.id, args=_args(), results=_results()
    )

    version, html = await widgets.render_version(
        widget=await widgets.get_widget(widget_id=built.widget_id, owner_id=DEMO_USER_ID),
        version_number=1,
        form="static",
    )
    assert version.spec["body"]["type"] == "table"
    assert version.spec["title"] == "Spending"
    assert version.model is None
    assert version.checks[0].passed is False
    assert "CHF 10&#39;598.77" in html


async def test_a_widget_needs_earlier_results_of_the_turn(session: AsyncSession) -> None:
    conversation = await make_conversation(session=session)
    widgets = _service(session=session, apertus=ScriptedApertus(decisions=[], specs=[]))

    with pytest.raises(BadRequestError, match="List the tools that fetch"):
        await widgets.build_widget(
            owner_id=DEMO_USER_ID, conversation_id=conversation.id, args=_args(), results=[]
        )


def test_widget_data_gives_rows_numbers_bookings_and_flat_lists() -> None:
    subscriptions = {
        "recurring": [
            {"payee": "Netflix", "last_paid_chf": "21.90", "price_changes": [{"new_price": 21.9}]}
        ]
    }
    movements = {"rows": [{"id": "BK-07", "amount_chf": "-12.50", "text": "Migros"}]}
    results = [
        *_results(),
        TurnResult(tool_call_id=uuid4(), tool_name="sum_by_month", result=MONTHS_RESULT),
        TurnResult(tool_call_id=uuid4(), tool_name="list_recurring", result=subscriptions),
        TurnResult(tool_call_id=uuid4(), tool_name="search_movements", result=movements),
    ]

    data = widget_data(results=results)

    assert set(data) == {
        "months",
        "sum_by_month_months",
        "recurring",
        "recurring_price_changes",
        "movements",
    }
    assert data["months"][1] == {
        "month": "2026-10",
        "money_out_chf": 10598.77,
        "booking_ids": ["BK-03"],
    }
    assert data["recurring"] == [{"payee": "Netflix", "last_paid_chf": 21.9}]
    assert data["recurring_price_changes"] == [{"parent": "Netflix", "new_price": 21.9}]
    assert data["movements"][0]["booking_ids"] == ["BK-07"]
    assert data["movements"][0]["amount_chf"] == -12.5
    # The stored tool results stay as they were.
    assert MONTHS_RESULT["months"][0]["money_out_chf"] == "17273.60"


def test_a_figure_shows_the_name_of_its_own_row() -> None:
    data = {"months": [{"month": "2026-01", "total_chf": 900.0}]}
    spec = WidgetSpec.model_validate(
        {
            "title": "Spending",
            "body": {"type": "kpi", "label": "October", "value": "months[0].total_chf"},
        }
    )

    page = render(spec=spec, data=data, form="static")

    assert "October · Jan 2026" in page


@pytest.mark.parametrize(
    ("label", "row", "shown"),
    [
        ("September", "Sep 2026", "September"),
        ("Seminar fees", "Sep 2026", "Seminar fees · Sep 2026"),
        ("Cooperative", "Coop", "Cooperative · Coop"),
        ("Paid to Coop", "Coop", "Paid to Coop"),
        ("Spending", "  ", "Spending"),
        (" ", "Sep 2026", "  · Sep 2026"),
    ],
)
def test_a_label_names_its_row_once(label: str, row: str, shown: str) -> None:
    assert _named(label=label, row=row) == shown


def test_money_out_is_drawn_as_a_positive_amount() -> None:
    month = {"month": "2026-10", "money_out_chf": "-10598.77", "money_in_chf": "7412.55"}
    results = [
        TurnResult(tool_call_id=uuid4(), tool_name="sum_by_month", result={"months": [month]})
    ]

    data = widget_data(results=results)

    assert data["months"][0]["money_out_chf"] == 10598.77
    assert data["months"][0]["money_in_chf"] == 7412.55


async def test_only_the_owner_reads_a_widget_version(
    client: httpx2.AsyncClient, session: AsyncSession
) -> None:
    conversation = await make_conversation(session=session)
    other = await make_conversation(session=session, owner_id=uuid4())
    repository = WidgetRepository(session=session)
    version = {
        "number": 1,
        "spec": GOOD_SPEC,
        "data": widget_data(results=_results()),
        "request": "Spending per month",
        "model": "fake",
        "latency_ms": 5,
        "tool_call_ids": [],
        "checks": [],
    }
    mine, _ = await repository.create_with_version(
        widget={
            "owner_id": DEMO_USER_ID,
            "conversation_id": conversation.id,
            "title": "Spending",
            "current_version": 1,
        },
        version=version,
    )
    theirs, _ = await repository.create_with_version(
        widget={
            "owner_id": other.owner_id,
            "conversation_id": other.id,
            "title": "Spending",
            "current_version": 1,
        },
        version=version,
    )

    page = await client.get(f"/api/widgets/{mine.id}/versions/1?form=static")
    foreign = await client.get(f"/api/widgets/{theirs.id}/versions/1")
    missing = await client.get(f"/api/widgets/{mine.id}/versions/2")

    assert page.status_code == 200
    assert page.json()["title"] == "Spending"
    assert "<svg" in page.json()["html"]
    assert foreign.status_code == 404
    assert missing.status_code == 404
