"""The boards gate: plan the four demo customers' boards cold, resolve and judge every one.

uv run python -m evals.boards.run --model glm --runs 3
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2

from app.clients.apertus import ApertusClient, Model
from app.clients.banking import BankingClient
from app.clients.openrouter import openrouter_client
from app.core.config import Settings
from app.core.errors import AppError
from app.features.board_plans.digest import tile_key
from app.features.board_plans.schemas import PlannedBoards, Signal
from app.features.board_plans.digest import HERO_TEMPLATES, HERO_TOP
from app.features.board_plans.service import (
    MAIN_MAX,
    MAIN_MIN,
    REQUEST_MAX,
    REQUEST_MIN,
    SIDE_MAX,
    SIDE_MIN,
    BoardPlanService,
)
from app.features.figure_checks.service import FigureCheckService
from app.features.ledger.service import LedgerService
from app.features.recurring_payments.service import RecurringPaymentService
from app.features.tiles.service import TileError, TileService
from evals.boards.cache import CachingTransport, run_label
from evals.boards.prompts import CRITERIA, Verdict, judge_prompt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PERSONAS = ROOT / "starter" / "resources" / "Demodaten" / "Personas"
CUSTOMERS = {
    "lukas": "Persona_1_Lukas_Meier.md",
    "jana": "Persona_2_Jana_Widmer.md",
    "daniela": "Persona_3_Daniela_Ruegg.md",
    "marco": "Persona_4_Marco_Baumann.md",
}
GLM = "z-ai/glm-5.3"
OPENROUTER_TIMEOUT_SECONDS = 300
LIST_SHOWN = 6
PARALLEL = {"glm": 12, "apertus": 4}


async def login(settings: Settings, customer: str) -> str:
    async with httpx2.AsyncClient(base_url=settings.banking_api_url, timeout=30) as http:
        response = await http.post(
            "/auth/login", json={"username": customer, "password": f"{customer}2026"}
        )
        response.raise_for_status()
        return response.json()["token"]


def _short(value: Any) -> Any:
    """A payload small enough for the judge, with every list cut."""
    if isinstance(value, dict):
        return {key: _short(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_short(item) for item in value[:LIST_SHOWN]]
    return value


def _judge_view(boards: list[dict[str, Any]]) -> str:
    lines = []
    for board in boards:
        lines.append(f'Board "{board["name"]}":')
        for index, tile in enumerate(board["tiles"], start=1):
            payload = dict(tile["payload"] or {})
            source = payload.pop("source", None)
            label = "" if source is None else f" (source: {source['label']})"
            lines.append(
                f'{index}. "{tile["title"]}" [{tile["template"]}] args {tile["args"]}{label}: '
                f"{json.dumps(_short(payload), ensure_ascii=False)}"
            )
    return "\n".join(lines)


def _hero_fits(plan: PlannedBoards, signals: list[Signal]) -> tuple[bool, str]:
    heroes = [s for s in signals if s.template in HERO_TEMPLATES][:HERO_TOP]
    keys = {tile_key(s.template, s.args or {}) for s in heroes if s.template is not None}
    hero = plan.boards[0].tiles[0] if plan.boards and plan.boards[0].tiles else None
    if hero is None:
        return False, "no tiles"
    fits = tile_key(hero.template, hero.args) in keys
    names = ", ".join(f"{s.id} {s.template}" for s in heroes)
    return fits, f"hero {hero.template}; strongest headline signals: {names}"


def _tile_count(plan: PlannedBoards, request: str | None) -> tuple[bool, str]:
    sizes = [len(board.tiles) for board in plan.boards]
    if request is not None:
        ok = len(sizes) == 1 and REQUEST_MIN <= sizes[0] <= REQUEST_MAX
    else:
        ok = bool(sizes) and MAIN_MIN <= sizes[0] <= MAIN_MAX
        ok = ok and all(SIDE_MIN <= size <= SIDE_MAX for size in sizes[1:])
    return ok, f"tiles per board: {sizes}"


def _no_repeats(plan: PlannedBoards) -> tuple[bool, str]:
    keys = [tile_key(t.template, t.args) for b in plan.boards for t in b.tiles]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    return not repeated, "" if not repeated else f"repeated: {repeated}"


async def run_one(
    service: BoardPlanService,
    tiles: TileService,
    judge: ApertusClient,
    customer: str,
    number: int,
    request: str | None,
    out: Path,
    semaphore: asyncio.Semaphore,
    settings: Settings,
    tag: str,
) -> dict[str, Any]:
    async with semaphore:
        run_label.set(f"{tag}{customer}-{number}-{request or 'first'}")
        token = await login(settings=settings, customer=customer)
        today = await service.ledger.get_today()
        started = time.perf_counter()
        record: dict[str, Any] = {"customer": customer, "run": number, "request": request}
        try:
            plan = await service.plan_boards(token=token, today=today, request=request)
        except AppError as exc:
            record |= {"error": str(exc), "acceptable": False}
            (out / f"{customer}-{number}.json").write_text(json.dumps(record, indent=1))
            return record
        record["seconds"] = round(time.perf_counter() - started, 1)
        digest = await service.read_customer(token=token, today=today)
        boards = []
        unresolved = []
        figures = FigureCheckService()
        for board in plan.boards:
            shown = []
            for tile in board.tiles:
                try:
                    payload = await tiles.resolve(tile.template, tile.args, token, today)
                    data = payload.model_dump(mode="json")
                    if figures.missing_figures(answer=tile.title, sources=[json.dumps(data)]):
                        unresolved.append(f"title figure: {tile.title}")
                except (TileError, AppError) as exc:
                    data = None
                    unresolved.append(f"{tile.title}: {exc}")
                shown.append(tile.model_dump(mode="json") | {"payload": data})
            boards.append({"name": board.name, "tiles": shown})
        checks: dict[str, tuple[bool, str]] = {
            "resolved": (not unresolved, "; ".join(unresolved)),
            "no_repeats": _no_repeats(plan=plan),
            "tile_count": _tile_count(plan=plan, request=request),
        }
        if request is None:
            checks["hero_fits"] = _hero_fits(plan=plan, signals=digest.signals)
        persona = (PERSONAS / CUSTOMERS[customer]).read_text(encoding="utf-8")
        verdict = await judge.structured(
            judge_prompt(
                rubric=(HERE / "rubric.md").read_text(encoding="utf-8"),
                persona=persona,
                boards=_judge_view(boards=boards),
                request=request,
            ),
            schema=Verdict,
            model=Model.SMART,
            purpose="board_judge",
            timeout_seconds=OPENROUTER_TIMEOUT_SECONDS,
        )
        judged = {c.name: (c.passed, c.reason) for c in verdict.content.criteria}
        for name in CRITERIA:
            judged.setdefault(name, (False, "the judge did not answer this criterion"))
        record |= {
            "plan": plan.model_dump(mode="json"),
            "boards": boards,
            "signals": [s.model_dump(mode="json") for s in digest.signals],
            "checks": {
                name: {"passed": ok, "detail": detail} for name, (ok, detail) in checks.items()
            },
            "judge": {name: {"passed": ok, "reason": why} for name, (ok, why) in judged.items()},
        }
        record["acceptable"] = all(ok for ok, _ in checks.values()) and all(
            ok for ok, _ in judged.values()
        )
        (out / f"{customer}-{number}.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print(f"{customer}-{number}: {'pass' if record['acceptable'] else 'FAIL'}", flush=True)
        return record


def _differs(records: list[dict[str, Any]]) -> None:
    """Fails a run whose main board has the same templates in order as another customer's."""
    for record in records:
        if "plan" not in record or record["request"] is not None:
            continue
        mine = [t["template"] for t in record["plan"]["boards"][0]["tiles"]]
        same = [
            f"{other['customer']}-{other['run']}"
            for other in records
            if "plan" in other
            and other["customer"] != record["customer"]
            and [t["template"] for t in other["plan"]["boards"][0]["tiles"]] == mine
        ]
        record["checks"]["differs"] = {"passed": not same, "detail": ", ".join(same)}
        record["acceptable"] = record["acceptable"] and not same


def _figure(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return "UNRESOLVED"
    return f"{payload['figure_chf']:,.2f}".replace(",", "'")


def _index(records: list[dict[str, Any]], model: str, spend: str) -> str:
    passed = sum(1 for r in records if r["acceptable"])
    lines = [f"# Boards gate, {model}", "", f"{passed} of {len(records)} acceptable.", ""]
    for customer in CUSTOMERS:
        mine = [r for r in records if r["customer"] == customer]
        if mine:
            ok = sum(1 for r in mine if r["acceptable"])
            lines.append(f"- {customer}: {ok} of {len(mine)}")
    lines += ["", f"OpenRouter: {spend}", ""]
    for record in records:
        verdict = "acceptable" if record["acceptable"] else "NOT acceptable"
        lines.append(f"## {record['customer']} {record['run']}: {verdict}")
        lines.append("")
        if "error" in record:
            lines += [f"Error: {record['error']}", ""]
            continue
        plan = record["plan"]
        lines += [
            f"- kind: {plan['kind']}",
            f"- question: {plan['question']}",
            f"- {record['seconds']} s, {plan['model']}",
            "",
        ]
        for board in record["boards"]:
            lines.append(f"**{board['name']}**")
            lines.append("")
            for tile in board["tiles"]:
                lines.append(
                    f"- {tile['title']} ({tile['template']}): {_figure(payload=tile['payload'])}"
                )
            lines.append("")
        if plan["ideas"]:
            lines.append("Ideas: " + "; ".join(idea["title"] for idea in plan["ideas"]))
            lines.append("")
        failed = [
            f"{name}: {c['detail']}" for name, c in record["checks"].items() if not c["passed"]
        ]
        failed += [
            f"judge {name}: {c['reason']}" for name, c in record["judge"].items() if not c["passed"]
        ]
        failed += [f"service {c['name']}: {c['detail']}" for c in plan["checks"] if not c["passed"]]
        if failed:
            lines += [f"- {line}" for line in failed]
            lines.append("")
    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["glm", "apertus"], default="glm")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--customers", default=",".join(CUSTOMERS))
    parser.add_argument("--request", default=None)
    # A new tag sends every prompt again, as new cold samples.
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    settings = Settings()  # pyright: ignore[reportCallIssue]
    transport = CachingTransport()
    http = httpx2.AsyncClient(transport=transport, timeout=OPENROUTER_TIMEOUT_SECONDS)
    judge = openrouter_client(settings=settings, model_name=GLM, http_client=http)
    planner = judge if args.model == "glm" else ApertusClient(settings=settings)
    banking = BankingClient(settings=settings)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = HERE / "runs" / f"{stamp}-{args.model}"
    out.mkdir(parents=True)
    semaphore = asyncio.Semaphore(PARALLEL[args.model])
    jobs = []
    for customer in args.customers.split(","):
        for number in range(1, args.runs + 1):
            # One ledger per run, as one request in the app has one.
            ledger = LedgerService(banking=banking)
            recurring = RecurringPaymentService(ledger=ledger)
            tiles = TileService(banking=banking, ledger=ledger, recurring=recurring)
            service = BoardPlanService(
                apertus=planner,
                tiles=tiles,
                ledger=ledger,
                recurring=recurring,
                figure_checks=FigureCheckService(),
            )
            jobs.append(
                run_one(
                    service=service,
                    tiles=tiles,
                    judge=judge,
                    customer=customer,
                    number=number,
                    request=args.request,
                    out=out,
                    semaphore=semaphore,
                    settings=settings,
                    tag=args.tag,
                )
            )
    records = list(await asyncio.gather(*jobs))
    _differs(records=records)
    for record in records:
        if "plan" in record:
            (out / f"{record['customer']}-{record['run']}.json").write_text(
                json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8"
            )
    spend = transport.spend.line()
    (out / "index.md").write_text(_index(records=records, model=args.model, spend=spend))
    print(f"{sum(r['acceptable'] for r in records)} of {len(records)} acceptable; {spend}")
    print(f"written to {out.relative_to(ROOT)}")
    await http.aclose()
    await banking.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
