"""Plays the four customers in the category center: each works through the review list once.

From `src/backend`, after a tune run of `evals.categorisation` left its categories stored:
    uv run python -m evals.categorisation_review --base-url http://localhost:8010 --out review.json
Only the "reviewed" half of the tune payees is touched; the other half measures whether corrections
carry over to payees nobody corrected. Held-out payees are never touched.
"""

import argparse
import asyncio
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from evals.categorisation import PERSONAS, load_gold, login, needs_review


def review_group(persona: str, payee: str) -> str:
    """Half of the tune payees are reviewed by the customer, the other half never."""
    digest = hashlib.sha1(f"review|{persona}|{payee}".encode()).digest()
    return "reviewed" if digest[0] % 2 == 0 else "untouched"


def decide(rows: list[dict[str, Any]], tags: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """What the customer clicks for one payee's flagged rows, from what they know is true."""
    truth = Counter(row["category"] for row in rows)
    flagged = [row for row in rows if needs_review(tag=tags[row["uid"]])]
    if not flagged:
        return []
    if len(truth) == 1:
        # One true category: a single "All are X" or "Apply to all" for the payee.
        category = next(iter(truth))
        return [{"scope": "payee", "key": rows[0]["payee"], "category": category}]
    # A payee whose bookings rightly differ: "Right" or a booking-only change per flagged row.
    return [
        {"scope": "booking", "key": f"{row['source']}:{row['id']}", "category": row["category"]}
        for row in flagged
    ]


async def review_persona(
    client: httpx.AsyncClient,
    base_url: str,
    banking_url: str,
    persona: str,
    gold: list[dict[str, Any]],
) -> dict[str, Any]:
    token, _ = await login(client=client, banking_url=banking_url, persona=persona)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(f"{base_url}/api/transaction-tags", headers=headers, timeout=120)
    response.raise_for_status()
    tags = {f"{persona}:{tag['row_source']}:{tag['row_id']}": tag for tag in response.json()}
    by_payee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in gold:
        if row["persona"] == persona and row["uid"] in tags:
            by_payee[row["payee"]].append(row)
    flagged_before = sum(
        needs_review(tag=tags[row["uid"]]) for rows in by_payee.values() for row in rows
    )
    actions: list[dict[str, str]] = []
    rows_changed = 0
    for payee, rows in by_payee.items():
        if review_group(persona=persona, payee=payee) != "reviewed":
            continue
        for action in decide(rows=rows, tags=tags):
            reply = await client.post(
                f"{base_url}/api/category-corrections", headers=headers, json=action, timeout=120
            )
            reply.raise_for_status()
            actions.append(action)
            rows_changed += reply.json()["rows_changed"]
    return {
        "flagged_before": flagged_before,
        "actions": len(actions),
        "payee_corrections": sum(action["scope"] == "payee" for action in actions),
        "booking_corrections": sum(action["scope"] == "booking" for action in actions),
        "rows_changed": rows_changed,
        "detail": actions,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--banking-url", default=get_settings().banking_api_url)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    gold = [row for row in load_gold() if row["split"] == "tune" and not row["loan"]]
    async with httpx.AsyncClient() as client:
        result = {
            persona: await review_persona(
                client=client,
                base_url=args.base_url,
                banking_url=args.banking_url,
                persona=persona,
                gold=gold,
            )
            for persona in PERSONAS
        }
    summary = {
        persona: {key: value for key, value in counts.items() if key != "detail"}
        for persona, counts in result.items()
    }
    print(json.dumps(summary, indent=1))  # noqa: T201
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
