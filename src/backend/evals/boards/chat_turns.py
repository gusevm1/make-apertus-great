"""Chat turns beside a board, against a running backend on the real gateway.

cd src/backend && uv run python -m evals.boards.chat_turns --base-url http://localhost:8012

Each turn runs on a fresh copy of a fixed board and in a fresh conversation, so neither an edit
nor the history of one turn reaches the next. Writes chat_runs/<timestamp>/turns.md and .json.
"""

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

BANK_URL = "http://localhost:8000/api"
SERVER_LINES = ["Both cases are on your board now.", "Both are on your board already."]
# The plan of the calls the server makes when the board decision made none.
FALLBACK_PLAN = "The tiles on the board answer this question."
RUNS_PATH = Path(__file__).with_name("chat_runs")
# Writes are refused without the page's origin.
ORIGIN = "http://localhost:3000"
TIMEOUT_SECONDS = 300
BOARD_TOOLS = {
    "add_tile",
    "change_tile",
    "rename_tile",
    "move_tile",
    "remove_tile",
    "rename_board",
    "create_board",
}
PROPOSE = "propose_context_entry"
# Words an answer beside a board never uses.
BANNED = re.compile(
    r"\btools?\b|\btile id\b|\bT\d\b|displayed in place|pre-existing|\bfield\b|\bWerkzeug",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
# A line break that is not part of an empty line between paragraphs.
SINGLE_BREAK = re.compile(r"(?<!\n)\n(?!\n)")
AMOUNT = re.compile(r"CHF\s?-?\d{1,3}(?:'\d{3})*(?:\.\d{2})?")

CHILD_SUPPORT_NOTE = (
    "The child support often comes late: on 22.10. last month. Always show both cases."
)
# The fixed boards the turns run on: template, args, title.
BOARDS: dict[str, list[tuple[str, dict[str, Any], str]]] = {
    "daniela": [
        (
            "payday_balance",
            {
                "account_id": "ACC-PRIV",
                "expected_from": "Patrick Rüegg",
                "expected_label": "the child support",
            },
            "What is left the day before the salary",
        ),
        ("bills_until_payday", {"account_id": "ACC-PRIV"}, "Bills due before the salary"),
        ("savings_goal", {"account_id": "ACC-SAV"}, "Emergency fund"),
        ("monthly_spending", {"months": 6}, "Where the money goes"),
        (
            "merchant_spending",
            {"merchants": ["Lidl", "Aldi", "Migros", "Coop"], "period": "last_3_months"},
            "Groceries",
        ),
        ("bill", {"payment_id": "PAY-0244"}, "Dentist bill for Lina"),
    ],
    "lukas": [
        ("net_worth", {"include_pension": False}, "What you own"),
        ("due_soon", {"days": 30}, "Due in the next 30 days"),
        ("pillar_3a", {}, "Pillar 3a"),
        ("monthly_spending", {"months": 6}, "Where the money goes"),
        ("savings_goal", {"account_id": "ACC-LT"}, "Savings"),
    ],
}


class Turn(BaseModel):
    name: str
    customer: str
    message: str
    # None: a chat-page question without a board.
    board: bool = True
    # The template of the tile the customer selected.
    selected: str | None = None
    # Board tools that must run; with an empty set, none may.
    board_tools: set[str] = set()
    # True: a proposal must come, False: none may, None: either.
    propose: bool | None = False
    # The template whose figure the answer must state, in Swiss format.
    figure_of: str | None = None
    # The alternative case of the payday tile must be in the answer too.
    alternative: bool = False
    # The payee of the bill flagged as a reminder must be named.
    reminder: bool = False
    # Any amount in CHF must be in the answer.
    any_amount: bool = False
    max_sentences: int = 5
    # Words no argument of the turn's calls may hold, such as the rent among subscriptions.
    forbidden_args: list[str] = []
    # Any board tool may run, or none.
    any_board_tools: bool = False
    # Messages sent first in the same conversation, beside the same board.
    before: list[str] = []
    # The answer must start with this, and contain these texts.
    starts_with: str | None = None
    contains: list[str] = []
    # A note saved as active before the turn, deleted after it.
    saved_note: str | None = None
    # The board's tiles for this turn instead of the customer's fixed board.
    tiles: list[tuple[str, dict[str, Any], str]] | None = None
    # A shop tile's merchants must hold these and none of those; a summary must hold this.
    merchants_in: list[str] = []
    merchants_out: list[str] = []
    summary_contains: str | None = None


TURNS = [
    Turn(
        name="payday",
        customer="daniela",
        message="Does my money last until payday?",
        board_tools={"add_tile"},
        propose=True,
        figure_of="payday_balance",
        alternative=True,
        starts_with="Yes",
        max_sentences=4,
    ),
    Turn(
        name="payday_again",
        customer="daniela",
        message="Does my money last until payday?",
        before=["Does my money last until payday?"],
        propose=None,
        any_board_tools=True,
        starts_with="Yes",
        contains=["124.96", "1'174.96"],
        max_sentences=4,
    ),
    Turn(
        name="payday_after_edit",
        customer="daniela",
        message="Does my money last until payday?",
        before=["Rename the emergency fund to Rainy day money."],
        propose=True,
        board_tools={"add_tile"},
        starts_with="Yes",
        contains=["124.96", "1'174.96"],
        max_sentences=4,
    ),
    Turn(
        name="payday_other_words",
        customer="daniela",
        message="Will I make it to my next salary?",
        before=["Does my money last until payday?"],
        propose=None,
        any_board_tools=True,
        starts_with="Yes",
        contains=["124.96", "1'174.96"],
        max_sentences=4,
    ),
    Turn(
        name="payday_from_board",
        customer="daniela",
        message="Looking at the board, do I make it to my salary?",
        propose=None,
        any_board_tools=True,
        starts_with="Yes",
        contains=["124.96", "1'174.96"],
        max_sentences=4,
    ),
    Turn(
        name="payday_note_saved",
        customer="daniela",
        message="Does my money last until payday?",
        saved_note=CHILD_SUPPORT_NOTE,
        propose=False,
        any_board_tools=True,
        starts_with="Yes",
        contains=["124.96", "1'174.96"],
        max_sentences=4,
    ),
    Turn(
        name="groceries",
        customer="daniela",
        message="Remove the monthly cash flow tile and add what I spend on groceries.",
        tiles=[
            BOARDS["daniela"][0],
            BOARDS["daniela"][1],
            ("income_and_spending", {"months": 6}, "Monthly cash flow"),
            BOARDS["daniela"][3],
        ],
        board_tools={"remove_tile", "add_tile"},
        merchants_in=["Lidl", "Aldi", "Migros", "Denner"],
        merchants_out=["Coop"],
        summary_contains="Groceries",
        contains=["1'092.35"],
        max_sentences=2,
    ),
    Turn(
        name="named_shops",
        customer="daniela",
        message="Show me what I spend at Migros and Denner this month.",
        tiles=[BOARDS["daniela"][0], BOARDS["daniela"][1], BOARDS["daniela"][3]],
        board_tools={"add_tile"},
        merchants_in=["Migros", "Denner"],
        merchants_out=["Lidl", "Aldi", "Coop"],
        propose=None,
        max_sentences=3,
    ),
    Turn(
        name="remove",
        customer="daniela",
        message="Remove the groceries tile.",
        board_tools={"remove_tile"},
        max_sentences=2,
    ),
    Turn(
        name="rename",
        customer="daniela",
        message="Rename the emergency fund to Rainy day money.",
        board_tools={"rename_tile"},
        max_sentences=2,
    ),
    Turn(
        name="move",
        customer="daniela",
        message="Move the dentist bill to the top.",
        board_tools={"move_tile"},
        max_sentences=2,
    ),
    Turn(
        name="migros_coop",
        customer="daniela",
        message="Show me what I spend at Migros and Coop each month.",
        board_tools={"add_tile"},
        propose=None,
        max_sentences=4,
    ),
    Turn(
        name="twelve_months",
        customer="daniela",
        message="Make the spending chart show 12 months.",
        board_tools={"change_tile"},
        max_sentences=3,
    ),
    Turn(
        name="subscriptions",
        customer="daniela",
        message="Add my subscriptions.",
        board_tools={"add_tile"},
        merchants_in=["Lebara", "Sunrise"],
        merchants_out=["Wohnbau", "Steueramt", "Assura", "Ratenwerk", "Stadt Winterthur"],
        summary_contains="Subscriptions",
        propose=None,
        max_sentences=4,
    ),
    Turn(
        name="subscriptions_lukas",
        customer="lukas",
        message="Add my subscriptions.",
        board_tools={"add_tile"},
        merchants_in=["Fitnesspark", "Swisscom", "Salt"],
        merchants_out=["Wohnbau", "Mythen", "Mobiliar", "Depot", "Glückskette", "EKZ"],
        summary_contains="Subscriptions",
        contains=["252.95"],
        propose=None,
        max_sentences=4,
    ),
    Turn(
        name="tile_meaning",
        customer="daniela",
        message="What is this tile telling me?",
        selected="payday_balance",
        figure_of="payday_balance",
    ),
    Turn(
        name="bills_wait",
        customer="daniela",
        message="Which of these can wait?",
        selected="bills_until_payday",
        reminder=True,
        max_sentences=3,
    ),
    Turn(
        name="lina_board",
        customer="daniela",
        message="Start a board about Lina.",
        board_tools={"create_board"},
        propose=None,
        max_sentences=3,
    ),
    Turn(
        name="health_board",
        customer="daniela",
        message="How much did I pay for health insurance this year?",
        contains=["2'985.40"],
        propose=None,
    ),
    Turn(
        name="japan",
        customer="lukas",
        message="We want to go to Japan in 2027. Keep an eye on that for me.",
        board_tools={"create_board"},
        propose=True,
        max_sentences=4,
    ),
    Turn(
        name="health_chat",
        customer="daniela",
        message="How much did I pay for health insurance this year?",
        board=False,
        contains=["2'985.40"],
        propose=None,
        max_sentences=8,
    ),
]


async def log_in(customer: str) -> str:
    async with httpx.AsyncClient(timeout=30) as bank:
        response = await bank.post(
            f"{BANK_URL}/auth/login",
            json={"username": customer, "password": f"{customer}2026"},
        )
        return response.raise_for_status().json()["token"]


async def ensure_boards(client: httpx.AsyncClient) -> None:
    boards = (await client.get("/api/boards")).raise_for_status().json()
    if not boards:
        (await client.post("/api/board-plans", json={})).raise_for_status()


async def fixed_board(
    client: httpx.AsyncClient, customer: str, tiles: list[tuple[str, dict[str, Any], str]] | None
) -> dict[str, Any]:
    board = (
        (await client.post("/api/boards", json={"name": "Eval board"})).raise_for_status().json()
    )
    for template, args, title in BOARDS[customer] if tiles is None else tiles:
        tile = await client.post(
            f"/api/boards/{board['id']}/tiles",
            json={"template": template, "args": args, "title": title},
        )
        if tile.status_code != 201:
            print(f"  {customer}: {template} cannot be drawn: {tile.text[:160]}")  # noqa: T201
    return (await client.get(f"/api/boards/{board['id']}")).raise_for_status().json()


async def stream_turn(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    event, done, error = "", None, None
    async with client.stream(
        "POST", f"{path}/messages", params={"stream": "true"}, json=body
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event in {"done", "error"}:
                data = json.loads(line[5:])
                done, error = (data, error) if event == "done" else (done, data)
    if done is None:
        raise RuntimeError(f"no answer: {error}")
    return done


async def cleanup(
    client: httpx.AsyncClient, path: str, calls: list[dict[str, Any]], board_id: str | None
) -> None:
    ids = {call["id"] for call in calls}
    proposals = (await client.get("/api/context-entries", params={"status": "proposed"})).json()
    for entry in proposals:
        if entry["source_id"] in ids:
            await client.delete(f"/api/context-entries/{entry['id']}")
    for call in calls:
        created = (call.get("result") or {}).get("board_id")
        if created is not None:
            await client.delete(f"/api/boards/{created}")
    await client.delete(path)
    if board_id is not None:
        await client.delete(f"/api/boards/{board_id}")


def swiss(amount: float) -> str:
    return f"{Decimal(str(amount)):,.2f}".replace(",", "'")


def problems_of(
    turn: Turn, answer: str, calls: list[dict[str, Any]], board: dict[str, Any] | None
) -> list[str]:
    problems: list[str] = []
    ran = {call["tool_name"] for call in calls if call["error"] is None}
    board_ran = ran & BOARD_TOOLS
    if turn.board_tools and not turn.board_tools <= board_ran:
        problems.append(f"expected {sorted(turn.board_tools)}, ran {sorted(board_ran) or 'none'}")
    if not turn.board_tools and board_ran and not turn.any_board_tools:
        problems.append(f"no board tool expected, ran {sorted(board_ran)}")
    arguments = json.dumps([call["arguments"] for call in calls if call["error"] is None])
    for word in turn.forbidden_args:
        if word in arguments:
            problems.append(f"{word} in the arguments")
    # The shops of the tile as drawn, which the server may have narrowed to the customer's payees.
    shops = [
        str(row.get("merchant") or row.get("payee"))
        for call in calls
        if call["error"] is None and call["tool_name"] in {"add_tile", "change_tile"}
        for row in ((call.get("result") or {}).get("figures") or {}).get("rows") or []
        if "merchant" in row or "payee" in row
    ] or [
        str(name)
        for call in calls
        if call["error"] is None and call["tool_name"] in {"add_tile", "change_tile"}
        for name in call["arguments"].get("merchants") or []
    ]
    for name in turn.merchants_in:
        if not any(name.casefold() in shop.casefold() for shop in shops):
            problems.append(f"{name} not among the shops {shops}")
    for name in turn.merchants_out:
        if any(name.casefold() in shop.casefold() for shop in shops):
            problems.append(f"{name} among the shops")
    summaries = " ".join(
        str((call.get("result") or {}).get("summary")) for call in calls if call["error"] is None
    )
    if turn.summary_contains is not None and turn.summary_contains not in summaries:
        problems.append(f"no summary with {turn.summary_contains!r}: {summaries}")
    if turn.propose is True and PROPOSE not in ran:
        problems.append("no profile note proposed")
    if turn.propose is False and PROPOSE in ran:
        problems.append("a profile note was proposed")
    # The server's lines under the answer are no part of what the model wrote.
    text = answer.split("\n\n✓")[0].strip()
    # The server's closing line is no sentence of the model's.
    for line in SERVER_LINES:
        text = text.replace(f"\n\n{line}", "")
    banned = BANNED.search(text)
    if turn.board and banned is not None:
        problems.append(f"banned word: {banned[0]!r}")
    if turn.starts_with is not None and not text.startswith(turn.starts_with):
        problems.append(f"does not start with {turn.starts_with!r}")
    for wanted in turn.contains:
        if wanted not in text:
            problems.append(f"{wanted} missing")
    if turn.board and re.search(r"\bNo,", text):
        problems.append("says 'No,'")
    if turn.board and re.search(r"\bmeaning\b|\btiles?\b|as stated", text, re.I):
        problems.append("speaks of meanings or tiles")
    if turn.board and re.search(r"\b(?:[1-9]\d{2,}|100)(?:\.\d+)?\s?%", text):
        problems.append("a percentage of 100 or more")
    if turn.board and re.search(r"[—–]", text):
        problems.append("a dash")
    if turn.board and re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}", text):
        problems.append("a year after a day")
    if turn.board and SINGLE_BREAK.search(text):
        problems.append("a single line break instead of a paragraph")
    sentences = len(SENTENCE_END.findall(re.sub(r"\b\d{1,2}\.\d{1,2}\.", "D", text)))
    if sentences > turn.max_sentences:
        problems.append(f"{sentences} sentences, at most {turn.max_sentences}")
    tiles = {} if board is None else {tile["template"]: tile for tile in board["tiles"]}
    if turn.figure_of is not None and turn.figure_of in tiles:
        figure = swiss(amount=tiles[turn.figure_of]["payload"]["figure_chf"])
        if figure not in text:
            problems.append(f"figure {figure} missing")
    if turn.alternative and "payday_balance" in tiles:
        other = tiles["payday_balance"]["payload"]["alternative"]
        if other is not None and swiss(amount=other["left_chf"]) not in text:
            problems.append(f"alternative {swiss(amount=other['left_chf'])} missing")
    if turn.reminder and "bills_until_payday" in tiles:
        flagged = [
            row["payee"]
            for row in tiles["bills_until_payday"]["payload"]["rows"]
            if row["flag"] == "reminder"
        ]
        if flagged and flagged[0].split()[0] not in text:
            problems.append(f"reminder payee {flagged[0]} not named")
    if turn.any_amount and AMOUNT.search(text) is None:
        problems.append("no amount in CHF")
    return problems


async def run_turn(base_url: str, turn: Turn, token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Origin": ORIGIN}
    async with httpx.AsyncClient(
        base_url=base_url, headers=headers, timeout=TIMEOUT_SECONDS
    ) as client:
        board = (
            await fixed_board(client=client, customer=turn.customer, tiles=turn.tiles)
            if turn.board
            else None
        )
        conversation = (
            (await client.post("/api/conversations", json={"title": "eval"}))
            .raise_for_status()
            .json()
        )
        path = f"/api/conversations/{conversation['id']}"
        body: dict[str, Any] = {"content": turn.message}
        if board is not None:
            body["board_id"] = board["id"]
            selected = next(
                (tile for tile in board["tiles"] if tile["template"] == turn.selected), None
            )
            if selected is not None:
                body["tile_id"] = selected["id"]
        calls: list[dict[str, Any]] = []
        active = (await client.get("/api/context-entries", params={"status": "active"})).json()
        # A note the customer saved in the page already: the turn must not propose it again.
        if turn.propose is True and any(entry["text"] == CHILD_SUPPORT_NOTE for entry in active):
            turn = turn.model_copy(update={"propose": False})
        saved_id = None
        if turn.saved_note is not None:
            saved = await client.post(
                "/api/context-entries", json={"kind": "fact", "text": turn.saved_note}
            )
            saved_id = saved.raise_for_status().json()["id"]
        try:
            for earlier in turn.before:
                await stream_turn(client=client, path=path, body={**body, "content": earlier})
            earlier_calls = (await client.get(f"{path}/tool-calls")).raise_for_status().json()
            started = time.perf_counter()
            reply = await stream_turn(client=client, path=path, body=body)
            seconds = time.perf_counter() - started
            every_call = (await client.get(f"{path}/tool-calls")).raise_for_status().json()
            calls = every_call[len(earlier_calls) :]
            answer = reply["content"]
            checks = (reply.get("provenance") or {}).get("checks", [])
            problems = problems_of(turn=turn, answer=answer, calls=calls, board=board)
            problems += [
                f"check {check['name']} failed: {check.get('detail')}"
                for check in checks
                if check["name"] == "figures_found" and not check["passed"]
            ]
        except Exception as exc:
            seconds = 0.0
            answer, checks, problems = "", [], [f"turn failed: {exc!r}"[:300]]
        finally:
            if saved_id is not None:
                await client.delete(f"/api/context-entries/{saved_id}")
            await cleanup(
                client=client,
                path=path,
                calls=(await client.get(f"{path}/tool-calls")).json(),
                board_id=None if board is None else board["id"],
            )
    return {
        "name": turn.name,
        "customer": turn.customer,
        "message": turn.message,
        "selected": turn.selected,
        "seconds": round(seconds, 1),
        "passed": not problems,
        "path": path_of(calls=calls),
        "problems": problems,
        "calls": [
            {
                "tool": call["tool_name"],
                "arguments": call["arguments"],
                "summary": (call.get("result") or {}).get("summary"),
                "plan": call.get("plan"),
                "error": call["error"],
            }
            for call in calls
        ],
        "answer": answer,
        "checks": checks,
    }


def path_of(calls: list[dict[str, Any]]) -> str:
    """Who chose the board calls: the model, the server's fallback, or nobody."""
    board = [call for call in calls if call["tool_name"] in BOARD_TOOLS]
    if not board:
        return "none"
    return "server" if all(call["plan"] == FALLBACK_PLAN for call in board) else "model"


def markdown(results: list[dict[str, Any]]) -> str:
    lines = ["# Chat turns beside a board", ""]
    passed = sum(result["passed"] for result in results)
    lines += [
        f"{passed} of {len(results)} passed.",
        "",
        "| Turn | Pass | Seconds |",
        "|---|---|---|",
    ]
    lines += [
        f"| {r['name']} | {'yes' if r['passed'] else 'no'} | {r['seconds']} | {r['path']} |"
        for r in results
    ]
    for result in results:
        lines += ["", f"## {result['name']} ({result['customer']})", "", f"> {result['message']}"]
        if result["selected"] is not None:
            lines.append(f"Selected tile: {result['selected']}")
        lines += ["", "Calls:"]
        for call in result["calls"]:
            outcome = call["summary"] if call["error"] is None else f"error: {call['error']}"
            lines.append(
                f"- {call['tool']} {json.dumps(call['arguments'], ensure_ascii=False)}: {outcome}"
            )
        lines += ["", "Answer:", "", result["answer"], ""]
        checks = ", ".join(
            f"{check['name']} {'ok' if check['passed'] else 'FAILED'} ({check.get('detail')})"
            for check in result["checks"]
        )
        lines.append(f"Checks: {checks or 'none'}. {result['seconds']} s.")
        if result["problems"]:
            lines += ["", "Problems:", *(f"- {problem}" for problem in result["problems"])]
    return "\n".join(lines) + "\n"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8012")
    parser.add_argument("--only", nargs="*", help="Run only these turns, by name.")
    options = parser.parse_args()
    tokens = {
        customer: await log_in(customer=customer)
        for customer in ("daniela", "lukas", "jana", "marco")
    }
    for token in tokens.values():
        headers = {"Authorization": f"Bearer {token}", "Origin": ORIGIN}
        async with httpx.AsyncClient(
            base_url=options.base_url, headers=headers, timeout=TIMEOUT_SECONDS
        ) as client:
            await ensure_boards(client=client)
    turns = [turn for turn in TURNS if not options.only or turn.name in options.only]
    results = []
    # One after the other: the gateway is shared and slow under load.
    for turn in turns:
        result = await run_turn(base_url=options.base_url, turn=turn, token=tokens[turn.customer])
        mark = "pass" if result["passed"] else "FAIL"
        problems = "; ".join(result["problems"])
        print(f"{mark} {turn.name:18} {result['seconds']:6.1f} s  {result['path']:6}  {problems}")  # noqa: T201
        results.append(result)
    folder = RUNS_PATH / datetime.now().strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True)
    (folder / "turns.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    (folder / "turns.md").write_text(markdown(results=results))
    print(f"{sum(r['passed'] for r in results)} of {len(results)} passed, see {folder}")  # noqa: T201
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
