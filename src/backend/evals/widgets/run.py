"""Widget benchmark: can Apertus write a dashboard widget? Writes results.md and a gallery."""

import argparse
import asyncio
import html
import json
import os
import re
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.clients.apertus import ApertusClient, Model
from app.clients.banking import BankingClient
from app.core.config import Settings
from app.core.errors import UpstreamError
from app.features.ledger.service import LedgerService
from evals.run import EvalSettings
from evals.widgets import prompts
from evals.widgets.data import build_all
from evals.widgets.page import (
    EditError,
    Edits,
    Scene,
    apply_edits,
    missing_numbers,
    page,
    render_scene,
    strip_fence,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS_MD = HERE / "results.md"
D3_PATH = HERE / "vendor" / "d3.v7.min.js"
VARIANTS: list[prompts.Variant] = ["html_svg", "html_d3", "shapes"]
MODES: list[prompts.Mode] = ["rewrite", "edits"]
REVISED_TASK = "monthly_spending"
WIDTHS = (360, 1000)
CHROME = os.environ.get(
    "CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
# Writing a whole widget can take longer than the app's 60 s per call.
APERTUS_TIMEOUT_SECONDS = 300
CHROME_TIMEOUT_SECONDS = 60
CHROME_PARALLEL = 4
REPORT = re.compile(r'<script type="application/json" id="bench-report">(.*?)</script>', re.DOTALL)


@dataclass
class Render:
    width: int
    errors: list[str]
    drawn: bool = False
    missing: list[str] = field(default_factory=list)
    overflows: bool = False
    uses_canvas: bool = False
    height: int = 0


@dataclass
class Run:
    variant: str
    model: str
    task: str
    revision: str | None = None
    mode: str | None = None
    seconds: float | None = None
    tokens_out: int | None = None
    chars: int | None = None
    failure: str | None = None
    page: str | None = None
    renders: list[Render] = field(default_factory=list)

    @property
    def name(self) -> str:
        return (
            self.task if self.revision is None else f"{self.task} + {self.revision} ({self.mode})"
        )

    @property
    def is_clean(self) -> bool:
        return (
            self.failure is None
            and len(self.renders) == len(WIDTHS)
            and all(not r.errors and r.drawn and not r.missing for r in self.renders)
        )


class Bench:
    def __init__(
        self, apertus: ApertusClient, data: dict[str, dict[str, Any]], d3: str | None, parallel: int
    ) -> None:
        self.apertus = apertus
        self.data = data
        self.d3 = d3
        self.llm_slots = asyncio.Semaphore(parallel)
        self.chrome_slots = asyncio.Semaphore(CHROME_PARALLEL)

    async def generate(self, run: Run) -> str | None:
        """Write the widget's first version; returns its code, or None when that failed."""
        variant = _variant(run=run)
        messages = prompts.generate_messages(
            variant=variant, task=run.task, data=self.data[run.task]
        )
        return await self._timed(
            run=run, call=self._write(variant=variant, model=run.model, messages=messages)
        )

    async def revise(self, run: Run, code: str, revision: str, mode: prompts.Mode) -> str | None:
        variant = _variant(run=run)
        messages = prompts.revise_messages(
            variant=variant,
            mode=mode,
            task=run.task,
            data=self.data[run.task],
            code=code,
            revision=revision,
        )
        if mode == "rewrite":
            return await self._timed(
                run=run, call=self._write(variant=variant, model=run.model, messages=messages)
            )

        async def edit() -> tuple[str, int | None]:
            result = await self.apertus.structured(
                messages, schema=Edits, model=Model(run.model), purpose="widget_bench_edits"
            )
            return apply_edits(code=code, edits=result.content), result.tokens_out

        return await self._timed(run=run, call=edit())

    async def render(self, run: Run, code: str) -> None:
        try:
            body = (
                render_scene(scene=Scene.model_validate_json(code))
                if run.variant == "shapes"
                else code
            )
        except ValidationError as error:
            run.failure = f"invalid shapes: {error.error_count()} errors"
            return
        path = RESULTS / "pages" / f"{run.variant}-{run.model}-{_slug(text=run.name)}.html"
        path.write_text(
            page(
                body=body,
                data=self.data[run.task],
                d3=self.d3 if run.variant == "html_d3" else None,
            )
        )
        run.page = path.name
        await self.check(run=run, path=path)

    async def check(self, run: Run, path: Path) -> None:
        """Load the page in Chrome at every width and record what the bridge reports."""
        request = prompts.request(task=run.task)
        if run.revision is not None:
            request += " " + prompts.change(revision=run.revision)
        run.renders = list(
            await asyncio.gather(
                *(
                    self._chrome(path=path, width=width, run=run, request=request)
                    for width in WIDTHS
                )
            )
        )

    async def _write(
        self, variant: prompts.Variant, model: str, messages: list[Any]
    ) -> tuple[str, int | None]:
        if variant == "shapes":
            result = await self.apertus.structured(
                messages, schema=Scene, model=Model(model), purpose="widget_bench_shapes"
            )
            return result.content.model_dump_json(exclude_none=True), result.tokens_out
        text = await self.apertus.chat(
            messages, model=Model(model), purpose=f"widget_bench_{variant}"
        )
        return strip_fence(text=text.content), text.tokens_out

    async def _timed(self, run: Run, call: Any) -> str | None:
        async with self.llm_slots:
            started = time.perf_counter()
            try:
                code, tokens_out = await call
            except (UpstreamError, EditError, ValidationError) as error:
                run.failure = str(error)[:200]
                return None
            finally:
                run.seconds = round(time.perf_counter() - started, 1)
        run.tokens_out = tokens_out
        run.chars = len(code)
        print(f"{run.variant:8} {run.model:5} {run.name:45} {run.seconds:6.1f}s", flush=True)  # noqa: T201
        return code

    async def _chrome(self, path: Path, width: int, run: Run, request: str) -> Render:
        async with self.chrome_slots:
            with tempfile.TemporaryDirectory() as profile:
                process = await asyncio.create_subprocess_exec(
                    CHROME,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--user-data-dir={profile}",
                    f"--window-size={width},900",
                    "--virtual-time-budget=5000",
                    "--dump-dom",
                    path.as_uri(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    output, _ = await asyncio.wait_for(
                        process.communicate(), CHROME_TIMEOUT_SECONDS
                    )
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    return Render(width=width, errors=["Chrome timed out"])
        match = REPORT.search(output.decode(errors="replace"))
        if match is None:
            return Render(width=width, errors=["the page never finished loading"])
        report = json.loads(match.group(1))
        return Render(
            width=width,
            errors=report["errors"],
            drawn=report["drawn"],
            missing=missing_numbers(
                texts=report["texts"], data=self.data[run.task], request=request
            ),
            overflows=report["overflows"],
            uses_canvas=report["uses_canvas"],
            height=report["height"],
        )


async def run_pair(bench: Bench, variant: str, model: str, tasks: list[str]) -> list[Run]:
    """One variant on one model: every task, then the revisions of the monthly spending chart."""
    runs = [Run(variant=variant, model=model, task=task) for task in tasks]
    codes = await asyncio.gather(*(bench.generate(run=run) for run in runs))
    await asyncio.gather(
        *(
            bench.render(run=run, code=code)
            for run, code in zip(runs, codes, strict=True)
            if code is not None
        )
    )
    base = next(
        (code for run, code in zip(runs, codes, strict=True) if run.task == REVISED_TASK), None
    )
    if base is None:
        return runs
    plan: list[tuple[str, prompts.Mode]] = [
        (revision, mode) for revision in prompts.REVISIONS for mode in MODES
    ]
    revisions = [
        Run(variant=variant, model=model, task=REVISED_TASK, revision=revision, mode=mode)
        for revision, mode in plan
    ]
    revised = await asyncio.gather(
        *(
            bench.revise(run=run, code=base, revision=revision, mode=mode)
            for run, (revision, mode) in zip(revisions, plan, strict=True)
        )
    )
    await asyncio.gather(
        *(
            bench.render(run=run, code=code)
            for run, code in zip(revisions, revised, strict=True)
            if code is not None
        )
    )
    return runs + revisions


def results_markdown(runs: list[Run], settings: Settings) -> str:
    fast = settings.llm_name if settings.llm_name_fast is None else settings.llm_name_fast
    lines = [
        "# Widget benchmark",
        "",
        f"Run on {date.today().isoformat()}. `smart` is `{settings.llm_name}`, `fast` is `{fast}`. "
        "A run is clean when the page loads without a JavaScript error at 360 px and 1000 px, "
        "draws something, and shows only numbers from `DATA` or the request.",
        "",
        "Clean says nothing about how the widget looks: a clean page can still overlap its labels "
        "or show a list instead of a chart. Judge that in `results/index.html`.",
        "",
        "| Variant | Model | Task | Clean | Seconds | Tokens out | Chars | 360 px | 1000 px |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        cells = [_render_cell(render=render) for render in run.renders]
        if len(cells) == 0:
            cells = [run.failure if run.failure is not None else "not rendered", ""]
        lines.append(
            f"| {run.variant} | {run.model} | {run.name} | {'yes' if run.is_clean else 'no'} | "
            f"{_or_dash(run.seconds)} | {_or_dash(run.tokens_out)} | {_or_dash(run.chars)} | "
            f"{_cell(text=cells[0])} | {_cell(text=cells[1])} |"
        )
    lines += [
        "",
        "## Summary",
        "",
        "| Variant | Model | Clean | Median seconds | Edits applied |",
        "|---|---|---|---|---|",
    ]
    for variant, model in dict.fromkeys((run.variant, run.model) for run in runs):
        pair = [run for run in runs if run.variant == variant and run.model == model]
        timed = [run.seconds for run in pair if run.seconds is not None and run.failure is None]
        edits = [run for run in pair if run.mode == "edits"]
        lines.append(
            f"| {variant} | {model} | {sum(run.is_clean for run in pair)} of {len(pair)} "
            f"({sum(run.is_clean for run in pair) / len(pair):.0%}) | "
            f"{_or_dash(round(statistics.median(timed), 1) if timed else None)} | "
            f"{sum(run.failure is None for run in edits)} of {len(edits)} |"
        )
    return "\n".join(lines) + "\n"


def gallery(runs: list[Run]) -> str:
    sections = []
    for run in runs:
        status = (
            "clean"
            if run.is_clean
            else (run.failure or "; ".join(_render_cell(render=r) for r in run.renders))
        )
        source = "" if run.page is None else html.escape(run.page)
        frames = "".join(
            f"<figure><figcaption>{render.width} px: "
            f"{html.escape(_render_cell(render=render))}</figcaption>"
            f'<iframe src="pages/{source}" sandbox="allow-scripts" width="{render.width}" '
            f'height="{min(max(render.height, 200), 900)}"></iframe></figure>'
            for render in run.renders
        )
        sections.append(
            f"<section><h2>{html.escape(f'{run.variant} · {run.model} · {run.name}')}</h2>"
            f"<p>{html.escape(status)} · {_or_dash(run.seconds)} s · "
            f"{_or_dash(run.tokens_out)} tokens</p>"
            f'<div class="frames">{frames}</div></section>'
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Widget benchmark</title><style>'
        "body{font:14px system-ui;margin:24px;color:#0B1E2A}"
        "section{border-top:1px solid #ccc;padding:12px 0}"
        ".frames{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}"
        "iframe{border:1px solid #ccc;background:#fff}figure{margin:0}"
        "figcaption{margin-bottom:4px}"
        "</style></head><body><h1>Widget benchmark</h1>" + "".join(sections) + "</body></html>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=VARIANTS)
    parser.add_argument(
        "--models",
        nargs="+",
        choices=[model.value for model in Model],
        default=[m.value for m in Model][::-1],
    )
    parser.add_argument("--tasks", nargs="+", choices=prompts.TASKS, default=prompts.TASKS)
    parser.add_argument("--parallel", type=int, default=3, help="Apertus calls at the same time")
    parser.add_argument(
        "--recheck", action="store_true", help="check the pages of the last run again, no Apertus"
    )
    args = parser.parse_args()
    if "html_d3" in args.variants and not D3_PATH.exists():
        parser.error(f"put d3 v7 (d3.min.js) at {D3_PATH}, or leave out html_d3")
    if not Path(CHROME).exists():
        parser.error(f"no Chrome at {CHROME}; set CHROME_PATH")
    d3 = D3_PATH.read_text(encoding="utf-8") if "html_d3" in args.variants else None
    (RESULTS / "pages").mkdir(parents=True, exist_ok=True)
    return asyncio.run(bench_all(args=args, d3=d3))


async def bench_all(args: argparse.Namespace, d3: str | None) -> int:
    settings = Settings(apertus_timeout_seconds=APERTUS_TIMEOUT_SECONDS)  # pyright: ignore[reportCallIssue]
    accounts = EvalSettings()
    async with httpx.AsyncClient(timeout=30) as bank:
        login = await bank.post(
            f"{settings.banking_api_url}/auth/login",
            json={"username": accounts.evals_username, "password": accounts.evals_password},
        )
    if login.status_code != 200:
        print(f"login failed: {login.status_code} {login.text[:200]}")  # noqa: T201
        return 1
    banking = BankingClient(settings=settings)
    apertus = ApertusClient(settings=settings)
    try:
        data = await build_all(ledger=LedgerService(banking=banking), token=login.json()["token"])
        bench = Bench(apertus=apertus, data=data, d3=d3, parallel=args.parallel)
        if args.recheck:
            runs = await recheck(bench=bench)
        else:
            pairs = [(variant, model) for model in args.models for variant in args.variants]
            results = await asyncio.gather(
                *(run_pair(bench=bench, variant=v, model=m, tasks=args.tasks) for v, m in pairs)
            )
            runs = [run for pair in results for run in pair]
    finally:
        await banking.close()
        await apertus.close()
    (RESULTS / "runs.json").write_text(json.dumps([asdict(run) for run in runs], indent=1))
    (RESULTS / "index.html").write_text(gallery(runs=runs))
    RESULTS_MD.write_text(results_markdown(runs=runs, settings=settings))
    print(f"Wrote {RESULTS_MD} and {RESULTS / 'index.html'}")  # noqa: T201
    return 0


async def recheck(bench: Bench) -> list[Run]:
    saved = json.loads((RESULTS / "runs.json").read_text())
    runs = [Run(**{**item, "renders": []}) for item in saved]
    await asyncio.gather(
        *(
            bench.check(run=run, path=RESULTS / "pages" / run.page)
            for run in runs
            if run.page is not None
        )
    )
    return runs


def _variant(run: Run) -> prompts.Variant:
    return next(variant for variant in VARIANTS if variant == run.variant)


def _render_cell(render: Render) -> str:
    problems = [f"{len(render.errors)} JS errors: {render.errors[0]}"] if render.errors else []
    problems += [] if render.drawn else ["draws nothing"]
    problems += [f"not in DATA: {', '.join(render.missing[:5])}"] if render.missing else []
    problems += ["scrolls sideways"] if render.overflows else []
    problems += ["canvas, so nothing to click"] if render.uses_canvas else []
    return "; ".join(problems) or "ok"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")[:160]


def _or_dash(value: Any) -> str:
    return "–" if value is None else str(value)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


if __name__ == "__main__":
    sys.exit(main())
