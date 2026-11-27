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

from app.clients.apertus import ApertusClient, Message, Model
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
    TemplateRefusedError,
    apply_edits,
    figure_problems,
    fill_template,
    page,
    render_scene,
    strip_fence,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS_MD = HERE / "results.md"
D3_PATH = HERE / "vendor" / "d3.v7.min.js"
VARIANTS: list[prompts.Variant] = ["html_svg", "html_d3", "shapes", "jinja"]
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
# Chrome fast-forwards timers by this much; it has to exceed REPORT_DELAY_MS in bridge.js.
VIRTUAL_TIME_MS = 5000
LOGIN_TIMEOUT_SECONDS = 30
FRAME_MIN_HEIGHT = 200
FRAME_MAX_HEIGHT = 900
SHOWN_MISSING = 5
SAVED_DATA = re.compile(r"<script>window\.DATA = (.*?);</script>", re.DOTALL)
REPORT = re.compile(r'<script type="application/json" id="bench-report">(.*?)</script>', re.DOTALL)


@dataclass
class Render:
    width: int
    errors: list[str]
    drawn: bool = False
    figures: list[str] = field(default_factory=list)
    overflows: bool = False
    uses_canvas: bool = False
    height: int = 0


@dataclass
class Run:
    variant: prompts.Variant
    model: str
    task: str
    revision: str | None = None
    mode: str | None = None
    # A revision of a broken first version can't be clean, so it is counted apart.
    base_is_clean: bool | None = None
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
            and all(not r.errors and r.drawn and not r.figures for r in self.renders)
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
        messages = prompts.generate_messages(
            variant=run.variant, task=run.task, data=self.data[run.task]
        )
        return await self._timed(
            run=run, call=self._write(variant=run.variant, model=run.model, messages=messages)
        )

    async def revise(self, run: Run, code: str, revision: str, mode: prompts.Mode) -> str | None:
        variant = run.variant
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
                messages=messages,
                schema=Edits,
                model=Model(run.model),
                purpose="widget_bench_edits",
            )
            return apply_edits(code=code, edits=result.content), result.tokens_out

        return await self._timed(run=run, call=edit())

    async def render(self, run: Run, code: str) -> None:
        body = code
        try:
            if run.variant == "shapes":
                body = render_scene(scene=Scene.model_validate_json(code))
            if run.variant == "jinja":
                body = fill_template(
                    template=code, data=self.data[run.task], request=_request(run=run)
                )
        except ValidationError as error:
            run.failure = f"invalid shapes: {error.error_count()} errors"
            return
        except TemplateRefusedError as error:
            run.failure = str(error)[:200]
            return
        path = RESULTS / "pages" / f"{run.variant}-{run.model}-{_slug(text=run.name)}.html"
        path.write_text(
            page(
                body=body,
                data=self.data[run.task],
                d3=self.d3 if run.variant == "html_d3" else None,
            ),
            encoding="utf-8",
        )
        run.page = path.name
        await self.check(run=run, path=path, data=self.data[run.task])

    async def check(self, run: Run, path: Path, data: dict[str, Any]) -> None:
        """Load the page in Chrome at every width and record what the bridge reports."""
        request = _request(run=run)
        run.renders = list(
            await asyncio.gather(
                *(
                    self._chrome(path=path, width=width, data=data, request=request)
                    for width in WIDTHS
                )
            )
        )

    async def _write(
        self, variant: prompts.Variant, model: str, messages: list[Message]
    ) -> tuple[str, int | None]:
        if variant == "shapes":
            result = await self.apertus.structured(
                messages=messages,
                schema=Scene,
                model=Model(model),
                purpose="widget_bench_shapes",
            )
            return result.content.model_dump_json(exclude_none=True), result.tokens_out
        text = await self.apertus.chat(
            messages=messages, model=Model(model), purpose=f"widget_bench_{variant}"
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

    async def _chrome(self, path: Path, width: int, data: dict[str, Any], request: str) -> Render:
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
                    f"--virtual-time-budget={VIRTUAL_TIME_MS}",
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
            figures=figure_problems(texts=report["texts"], data=data, request=request),
            overflows=report["overflows"],
            uses_canvas=report["uses_canvas"],
            height=report["height"],
        )


async def run_pair(
    bench: Bench, variant: prompts.Variant, model: str, tasks: list[str]
) -> list[Run]:
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
    base_run, base = next(
        (
            (run, code)
            for run, code in zip(runs, codes, strict=True)
            if run.task == REVISED_TASK and code is not None
        ),
        (None, None),
    )
    if base_run is None or base is None:
        return runs
    plan: list[tuple[str, prompts.Mode]] = [
        (revision, mode) for revision in prompts.REVISIONS for mode in MODES
    ]
    revisions = [
        Run(
            variant=variant,
            model=model,
            task=REVISED_TASK,
            revision=revision,
            mode=mode,
            base_is_clean=base_run.is_clean,
        )
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
        "draws something, shows no NaN or undefined, and passes the chat's own figure check "
        "(`app/features/figure_checks`) against `DATA` and the request.",
        "",
        "Clean says nothing about how the widget looks: a clean page can still overlap its labels "
        "or show a list instead of a chart. Judge that in `results/index.html`.",
        "",
        "| Variant | Model | Task | Clean | Seconds | Tokens out | Chars | 360 px | 1000 px |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        cells = [_render_cell(render=render, limit=SHOWN_MISSING) for render in run.renders]
        if len(cells) == 0:
            cells = [run.failure if run.failure is not None else "not rendered", ""]
        clean = "yes" if run.is_clean else "no"
        if run.base_is_clean is False:
            clean += " (first version broken)"
        lines.append(
            f"| {run.variant} | {run.model} | {run.name} | {clean} | "
            f"{_or_dash(run.seconds)} | {_or_dash(run.tokens_out)} | {_or_dash(run.chars)} | "
            f"{_cell(text=cells[0])} | {_cell(text=cells[1])} |"
        )
    lines += [
        "",
        "## Summary",
        "",
        "Revisions count only where the first version was clean, so a broken first version "
        "doesn't count five times.",
        "",
        "| Variant | Model | Tasks clean | Median seconds | Revisions clean | Edits applied |",
        "|---|---|---|---|---|---|",
    ]
    for variant, model in dict.fromkeys((run.variant, run.model) for run in runs):
        pair = [run for run in runs if run.variant == variant and run.model == model]
        tasks = [run for run in pair if run.revision is None]
        timed = [run.seconds for run in tasks if run.seconds is not None and run.failure is None]
        revisions = [run for run in pair if run.base_is_clean is True]
        edits = [run for run in pair if run.mode == "edits"]
        lines.append(
            f"| {variant} | {model} | {_share(runs=tasks)} | "
            f"{_or_dash(round(statistics.median(timed), 1) if len(timed) > 0 else None)} | "
            f"{_share(runs=revisions)} | "
            f"{sum(run.failure is None for run in edits)} of {len(edits)} |"
        )
    return "\n".join(lines) + "\n"


def _share(runs: list[Run]) -> str:
    if len(runs) == 0:
        return "–"
    clean = sum(run.is_clean for run in runs)
    return f"{clean} of {len(runs)} ({clean / len(runs):.0%})"


def gallery(runs: list[Run]) -> str:
    sections = []
    for run in runs:
        status = "clean" if run.is_clean else "not clean"
        if run.failure is not None:
            status = run.failure
        source = "" if run.page is None else html.escape(run.page)
        frames = "".join(
            f"<figure><figcaption>{render.width} px: "
            f"{html.escape(_render_cell(render=render, limit=None))}</figcaption>"
            f'<iframe src="pages/{source}" sandbox="allow-scripts" width="{render.width}" '
            f'height="{min(max(render.height, FRAME_MIN_HEIGHT), FRAME_MAX_HEIGHT)}">'
            "</iframe></figure>"
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
    async with httpx.AsyncClient(timeout=LOGIN_TIMEOUT_SECONDS) as bank:
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
    (RESULTS / "runs.json").write_text(
        json.dumps([asdict(run) for run in runs], indent=1), encoding="utf-8"
    )
    (RESULTS / "index.html").write_text(gallery(runs=runs), encoding="utf-8")
    RESULTS_MD.write_text(results_markdown(runs=runs, settings=settings), encoding="utf-8")
    print(f"Wrote {RESULTS_MD} and {RESULTS / 'index.html'}")  # noqa: T201
    return 0


async def recheck(bench: Bench) -> list[Run]:
    """Check the saved pages again, each against the DATA it was written for."""
    saved = json.loads((RESULTS / "runs.json").read_text(encoding="utf-8"))
    runs = [Run(**{**item, "renders": []}) for item in saved]
    checks = []
    for run in runs:
        if run.page is None:
            continue
        path = RESULTS / "pages" / run.page
        match = SAVED_DATA.search(path.read_text(encoding="utf-8"))
        if match is None:
            run.failure = "the saved page has no DATA"
            continue
        checks.append(bench.check(run=run, path=path, data=json.loads(match.group(1))))
    await asyncio.gather(*checks)
    firsts = {
        (run.variant, run.model): run
        for run in runs
        if run.task == REVISED_TASK and run.revision is None
    }
    for run in runs:
        if run.revision is not None:
            run.base_is_clean = firsts[(run.variant, run.model)].is_clean
    return runs


def _request(run: Run) -> str:
    """The customer's words behind a run; numbers in them may appear on the page."""
    request = prompts.request(task=run.task)
    if run.revision is not None:
        request += " " + prompts.change(revision=run.revision)
    return request


def _render_cell(render: Render, limit: int | None) -> str:
    problems = [f"{len(render.errors)} JS errors: {render.errors[0]}"] if render.errors else []
    problems += [] if render.drawn else ["draws nothing"]
    if len(render.figures) > 0:
        shown = render.figures if limit is None else render.figures[:limit]
        more = len(render.figures) - len(shown)
        problems.append(f"figures: {', '.join(shown)}" + (f" (+{more})" if more > 0 else ""))
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
