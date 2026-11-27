"""Runs every eval question against a running backend and writes evals/report/index.html."""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from evals.report import Entry, plan_questions, render_page
from evals.run import (
    FIGURES_PATH,
    GUARDRAILS_PATH,
    QUESTIONS_PATH,
    EvalSettings,
    format_result,
    load_questions,
    run_questions,
)

PAGE_PATH = Path(__file__).with_name("index.html")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=EvalSettings().evals_base_url)
    args = parser.parse_args()
    if args.base_url is None:
        parser.error("set EVALS_BASE_URL or pass --base-url http://localhost:<your backend port>")
    planned = plan_questions(
        tool_choice=load_questions(path=QUESTIONS_PATH),
        figures=load_questions(path=FIGURES_PATH),
        guardrails=load_questions(path=GUARDRAILS_PATH),
    )
    results = run_questions(
        questions=[item.question for item in planned],
        base_url=args.base_url,
        settings=EvalSettings(),
    )
    entries: list[Entry] = []
    # A run takes over an hour; a crash late in it still leaves a page of what was asked.
    try:
        async for result in results:
            entries.append(Entry(criterion=planned[len(entries)].criterion, result=result))
            print(f"{len(entries):3}/{len(planned)} {format_result(result=result)}", flush=True)  # noqa: T201
    finally:
        page = render_page(entries=entries, base_url=args.base_url, finished_at=datetime.now())
        PAGE_PATH.write_text(page, encoding="utf-8")
        print(f"Wrote {PAGE_PATH} with {len(entries)} of {len(planned)} questions")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
