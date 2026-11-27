import httpx2
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.tool_calls.schemas import ToolDecision, ToolRequest
from tests.conftest import FakeApertus
from tests.factories import make_conversation


async def test_turn_reads_the_accounts_and_sums_them_on_the_server(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    url = f"/api/conversations/{conversation.id}"
    request = ToolRequest(reason="The balances.", tool="list_accounts", arguments={})
    apertus.decisions = [ToolDecision(plan="Read the accounts.", calls=[request]).model_dump_json()]

    reply = await client.post(f"{url}/messages", json={"content": "How much money do I have?"})

    assert reply.status_code == 201
    (call,) = (await client.get(f"{url}/tool-calls")).json()
    assert (call["tool_name"], call["error"]) == ("list_accounts", None)
    assert [account["account_id"] for account in call["result"]["accounts"]] == [
        "ACC-PRIV",
        "ACC-TAX",
    ]
    # 9716.33 + 4638.04, exact because the server adds decimals, not floats
    assert call["result"]["total_balance_chf"] == "14354.37"


async def test_requests_without_the_e_banking_token_are_refused(client: httpx2.AsyncClient) -> None:
    for headers in ({"Authorization": ""}, {"Authorization": "Bearer someone-else"}):
        response = await client.get("/api/conversations", headers=headers)

        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"


async def test_prompt_says_which_page_the_customer_has_open(
    client: httpx2.AsyncClient, session: AsyncSession, apertus: FakeApertus
) -> None:
    conversation = await make_conversation(session=session)
    page = {"title": "Privatkonto", "account_name": "Privatkonto"}

    reply = await client.post(
        f"/api/conversations/{conversation.id}/messages", json={"content": "Hi", "page": page}
    )

    assert reply.status_code == 201
    decision, answer = apertus.requests
    # The tool decision has to know the page too, or "this account" means nothing to it.
    for request in (decision, answer):
        question = request["messages"][1]["content"]
        assert "page 'Privatkonto' open, with the account 'Privatkonto' selected" in question
        assert question.endswith("Hi")
        assert "Friday, 27.11.2026" in request["messages"][0]["content"]
