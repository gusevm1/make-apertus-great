"""Categorisation eval: scores Apertus's categories and certainty against Claude's gold labels.

Run against a running backend on the real gateway, from `src/backend`:
    uv run python -m evals.categorisation --base-url http://localhost:8010 --split tune
It clears the stored categories of the chosen split's bookings, has the backend categorise them
again through `POST /api/categorisations`, and compares every booking with its gold label.
The held-out split is for the final report only: never tune on its results.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import delete, tuple_
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.auth import owner_id
from app.core.config import get_settings
from app.features.transaction_tags.models import CategoryCorrectionORM, TransactionTagORM

GOLD_PATH = Path(__file__).with_name("categorisation_gold.jsonl")
PERSONAS = ("lukas", "jana", "daniela", "marco")
HELD_OUT_SHARE = 4  # one payee in four, per customer, is held out
CATEGORISE_TIMEOUT_SECONDS = 900
MAX_CATEGORISE_CALLS = 6
POLL_SECONDS = 5


def split_of(persona: str, payee: str) -> str:
    """Held out by payee, so no correction or example of a held-out payee reaches tuning."""
    digest = hashlib.sha1(f"{persona}|{payee}".encode()).digest()
    return "heldout" if digest[0] % HELD_OUT_SHARE == 0 else "tune"


def load_gold() -> list[dict[str, Any]]:
    return [json.loads(line) for line in GOLD_PATH.read_text().splitlines() if line.strip()]


async def login(client: httpx.AsyncClient, banking_url: str, persona: str) -> tuple[str, str]:
    response = await client.post(
        f"{banking_url}/auth/login", json={"username": persona, "password": f"{persona}2026"}
    )
    response.raise_for_status()
    token = response.json()["token"]
    customer = await client.get(
        f"{banking_url}/customer", headers={"Authorization": f"Bearer {token}"}
    )
    customer.raise_for_status()
    return token, customer.json()["customer_id"]


async def clear_tags(rows: list[dict[str, Any]], owner: Any, keep_corrections: bool) -> None:
    """Forget the stored categories of these rows, so the backend categorises them again."""
    engine = create_async_engine(get_settings().database_url)
    keys = [(row["source"], row["id"]) for row in rows]
    async with engine.begin() as connection:
        for start in range(0, len(keys), 1000):
            await connection.execute(
                delete(TransactionTagORM).where(
                    TransactionTagORM.owner_id == owner,
                    tuple_(TransactionTagORM.row_source, TransactionTagORM.row_id).in_(
                        keys[start : start + 1000]
                    ),
                )
            )
        if not keep_corrections:
            await connection.execute(
                delete(CategoryCorrectionORM).where(CategoryCorrectionORM.owner_id == owner)
            )
    await engine.dispose()


async def finished_run(
    client: httpx.AsyncClient, base_url: str, headers: dict[str, str]
) -> dict[str, Any]:
    """Start a background categorisation and wait until it is done or failed."""
    response = await client.post(f"{base_url}/api/categorisations", headers=headers, timeout=60)
    response.raise_for_status()
    run = response.json()
    deadline = time.monotonic() + CATEGORISE_TIMEOUT_SECONDS
    while run["status"] in ("queued", "running") and time.monotonic() < deadline:
        await asyncio.sleep(POLL_SECONDS)
        polled = await client.get(
            f"{base_url}/api/categorisations/{run['id']}", headers=headers, timeout=60
        )
        polled.raise_for_status()
        run = polled.json()
    return run


async def categorise_persona(
    client: httpx.AsyncClient,
    base_url: str,
    banking_url: str,
    persona: str,
    rows: list[dict[str, Any]],
    keep_corrections: bool,
    score_only: bool,
) -> dict[str, dict[str, Any]]:
    token, customer_id = await login(client=client, banking_url=banking_url, persona=persona)
    headers = {"Authorization": f"Bearer {token}"}
    if not score_only:
        await clear_tags(
            rows=rows, owner=owner_id(customer_id=customer_id), keep_corrections=keep_corrections
        )
        # Skipped rows stay untagged for the next call, as in the product, so call again.
        for attempt in range(1, MAX_CATEGORISE_CALLS + 1):
            started = time.monotonic()
            run = await finished_run(client=client, base_url=base_url, headers=headers)
            elapsed = time.monotonic() - started
            counts = {
                key: run[key]
                for key in ("status", "tagged_by_model", "tagged_by_correction", "skipped")
            }
            print(f"  {persona} #{attempt}: {counts} in {elapsed:.0f} s", file=sys.stderr)  # noqa: T201
            if run["status"] == "done" and run["skipped"] == 0:
                break
    tags = await client.get(f"{base_url}/api/transaction-tags", headers=headers, timeout=120)
    tags.raise_for_status()
    return {f"{persona}:{tag['row_source']}:{tag['row_id']}": tag for tag in tags.json()}


def needs_review(tag: dict[str, Any]) -> bool:
    """The category center's rule: unsure, unrated, or unlike the payee's usual category."""
    if tag["category_confirmed"]:
        return False
    if tag["category"] != tag["payee_usual_category"]:
        return True
    return tag["category_certainty"] != "high"


def score(gold: list[dict[str, Any]], tags: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Model accuracy, confusions and certainty calibration; rule and customer rows apart."""
    model_rows, by_customer, missing = [], [], []
    for row in gold:
        tag = tags.get(row["uid"])
        if tag is None:
            missing.append(row)
        elif tag["category_set_by"] == "model":
            model_rows.append((row, tag))
        else:
            by_customer.append((row, tag))
    scored = len(model_rows) + len(missing)
    right = [(row, tag) for row, tag in model_rows if tag["category"] == row["category"]]
    wrong = [(row, tag) for row, tag in model_rows if tag["category"] != row["category"]]
    calibration: dict[str, dict[str, int]] = defaultdict(lambda: {"right": 0, "wrong": 0})
    for row, tag in model_rows:
        level = tag["category_certainty"] or "unknown"
        calibration[level]["right" if tag["category"] == row["category"] else "wrong"] += 1
    flagged = [(row, tag) for row, tag in model_rows if needs_review(tag)]
    hard_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row, tag in model_rows:
        for kind in row["hard"]:
            hard_counts[kind][0] += tag["category"] == row["category"]
            hard_counts[kind][1] += 1
    return {
        "scored": scored,
        "accuracy": len(right) / scored if scored else 0.0,
        "missing": len(missing),
        "fixed_by_rule_or_customer": len(by_customer),
        "fixed_right": sum(tag["category"] == row["category"] for row, tag in by_customer),
        "wrong_and_high": sum(tag["category_certainty"] == "high" for _, tag in wrong),
        "calibration": dict(calibration),
        "review_load": len(flagged) / len(model_rows) if model_rows else 0.0,
        "review_catches_wrong": (
            sum(needs_review(tag) for _, tag in wrong) / len(wrong) if wrong else 1.0
        ),
        "matrix": {
            gold_category: dict(
                Counter(
                    tag["category"] for row, tag in model_rows if row["category"] == gold_category
                )
            )
            for gold_category in sorted({row["category"] for row, _ in model_rows})
        },
        "confusions": Counter(
            f"{row['category']} -> {tag['category']}" for row, tag in wrong
        ).most_common(15),
        "hard": {
            kind: f"{right_count}/{total}" for kind, (right_count, total) in hard_counts.items()
        },
        "per_persona": {
            persona: (
                sum(1 for row, tag in right if row["persona"] == persona),
                sum(1 for row, _ in model_rows if row["persona"] == persona)
                + sum(1 for row in missing if row["persona"] == persona),
            )
            for persona in PERSONAS
        },
        "wrong_examples": [
            {
                "uid": row["uid"],
                "text": row["seen"].get("text"),
                "counterparty": row["seen"].get("counterparty"),
                "amount_chf": row["seen"]["amount_chf"],
                "gold": row["category"],
                "model": tag["category"],
                "certainty": tag["category_certainty"],
            }
            for row, tag in wrong
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--banking-url", default=get_settings().banking_api_url)
    parser.add_argument("--split", choices=("tune", "heldout"), required=True)
    parser.add_argument("--keep-corrections", action="store_true")
    # Scores the categories stored now, without categorising again.
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--label", default="run")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    gold = [row for row in load_gold() if row["split"] == args.split and not row["loan"]]
    async with httpx.AsyncClient() as client:
        tags: dict[str, dict[str, Any]] = {}
        for persona in PERSONAS:
            rows = [row for row in gold if row["persona"] == persona]
            tags.update(
                await categorise_persona(
                    client=client,
                    base_url=args.base_url,
                    banking_url=args.banking_url,
                    persona=persona,
                    rows=rows,
                    keep_corrections=args.keep_corrections,
                    score_only=args.score_only,
                )
            )
    result = score(gold=gold, tags=tags)
    result["predictions"] = {
        row["uid"]: {
            key: tags[row["uid"]][key]
            for key in ("category", "category_set_by", "category_certainty", "payee_usual_category")
        }
        for row in gold
        if row["uid"] in tags
    }
    result["label"] = args.label
    result["split"] = args.split
    summary = {
        key: value
        for key, value in result.items()
        if key not in ("wrong_examples", "matrix", "predictions")
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))  # noqa: T201
    if args.out is not None:
        args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
