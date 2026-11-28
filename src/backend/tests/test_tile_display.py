import httpx2

SHOPS = {"merchants": ["Migros", "Wohnbau"], "period": "last_month"}


async def _create(client: httpx2.AsyncClient, template: str, args: dict) -> httpx2.Response:
    board = (await client.post("/api/boards", json={"name": "Mine"})).json()
    return await client.post(
        f"/api/boards/{board['id']}/tiles", json={"template": template, "args": args}
    )


async def test_shops_come_largest_first_unless_the_tile_asks_smallest_first(
    client: httpx2.AsyncClient,
) -> None:
    default = (await _create(client=client, template="merchant_spending", args=SHOPS)).json()
    smallest = (
        await _create(
            client=client,
            template="merchant_spending",
            args={**SHOPS, "order": "smallest_first", "view": "donut"},
        )
    ).json()

    assert [row["merchant"] for row in default["payload"]["rows"]] == ["Wohnbau", "Migros"]
    assert default["args"] == SHOPS
    assert default["payload"]["view"] == "bars"
    assert [row["merchant"] for row in smallest["payload"]["rows"]] == ["Migros", "Wohnbau"]
    assert smallest["payload"]["rows"][1]["share"] == 1
    assert smallest["payload"]["view"] == "donut"


async def test_a_view_the_template_cannot_draw_is_refused(client: httpx2.AsyncClient) -> None:
    line = await _create(client=client, template="monthly_spending", args={"view": "line"})
    donut = await _create(client=client, template="monthly_spending", args={"view": "donut"})
    due = await _create(client=client, template="due_soon", args={"view": "donut"})

    assert line.status_code == 201, line.text
    assert line.json()["payload"]["view"] == "line"
    assert donut.status_code == 400
    assert due.status_code == 400
