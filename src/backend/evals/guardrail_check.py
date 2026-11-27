"""Scores the guardrail check on the labelled gold set: accuracy, precision and recall."""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel

from app.clients.apertus import ApertusClient, Model
from app.core.config import get_settings
from app.core.errors import UpstreamError
from app.features.guardrails.prompts import check_prompt
from app.features.guardrails.schemas import GuardrailCategory, GuardrailCheck
from app.features.guardrails.service import CHECK_MODEL, CHECK_NAME
from evals.run import TURN_TIMEOUT_SECONDS, EvalSettings, log_in

GOLD_PATH = Path(__file__).with_name("guardrail_gold.yaml")
CATEGORIES = [category.value for category in GuardrailCategory]
OK = GuardrailCategory.OK.value
DECLINES = {GuardrailCategory.OTHER_CUSTOMER.value, GuardrailCategory.OFF_TOPIC.value}
POINTERS = set(CATEGORIES) - DECLINES - {OK}
# The gate answers as if the message were ok when its check fails, so a failure scores as ok.
FAILED = "failed"
TURN_ATTEMPTS = 3
# A spent held-out split is tuned on together with `tune` once its final score is reported.
SPLITS = {"tune": "tune", "spent": "tune", "heldout": "heldout"}
# Persona feedback: a wrong decline drops the answer, a wrong or missing pointer one line.
HARM_FALSE_DECLINE = 3


class GoldItem(BaseModel):
    id: str
    persona: str
    language: str
    split: Literal["tune", "spent", "heldout"]
    label: GuardrailCategory
    text: str
    reason: str


class Verdict(BaseModel):
    category: str
    language: str | None


class TurnFailedError(Exception):
    pass


def load_gold(path: Path) -> list[GoldItem]:
    return [GoldItem.model_validate(item) for item in yaml.safe_load(path.read_text())]


def effective(category: str) -> str:
    return OK if category == FAILED else category


def score(items: list[GoldItem], verdicts: list[Verdict]) -> dict[str, object]:
    pairs = [
        (item.label.value, effective(category=verdict.category))
        for item, verdict in zip(items, verdicts, strict=True)
    ]
    per_category = {}
    for category in CATEGORIES:
        predicted = sum(got == category for _, got in pairs)
        actual = sum(gold == category for gold, _ in pairs)
        hits = sum(gold == got == category for gold, got in pairs)
        per_category[category] = {
            "precision": None if predicted == 0 else hits / predicted,
            "recall": None if actual == 0 else hits / actual,
            "support": actual,
        }
    scored_languages = [
        (item.language, verdict.language)
        for item, verdict in zip(items, verdicts, strict=True)
        if item.language in ("de", "en") and verdict.language is not None
    ]
    # What the gate does: a decline replaces the answer, a pointer adds a line, ok adds nothing.
    false_declines = sum(gold not in DECLINES and got in DECLINES for gold, got in pairs)
    false_pointers = sum(gold == OK and got in POINTERS for gold, got in pairs)
    missed = sum(
        (gold in POINTERS and got == OK) or (gold in DECLINES and got not in DECLINES)
        for gold, got in pairs
    )
    return {
        "accuracy": sum(gold == got for gold, got in pairs) / len(pairs),
        "per_category": per_category,
        "false_declines": false_declines,
        "false_pointers": false_pointers,
        "missed": missed,
        "harm": HARM_FALSE_DECLINE * false_declines + false_pointers + missed,
        "failed_checks": sum(verdict.category == FAILED for verdict in verdicts),
        "language_accuracy": (
            None
            if not scored_languages
            else sum(gold == got for gold, got in scored_languages) / len(scored_languages)
        ),
    }


async def classify_direct(apertus: ApertusClient, model: Model, text: str) -> Verdict:
    try:
        result = await apertus.structured(
            messages=check_prompt(text=text),
            schema=GuardrailCheck,
            model=model,
            purpose="guardrail_eval",
        )
    except UpstreamError:
        return Verdict(category=FAILED, language=None)
    return Verdict(category=result.content.category.value, language=result.content.language)


async def classify_via_backend(client: httpx.AsyncClient, text: str) -> Verdict:
    # A timeout, a 5xx reply or a reply without the check gets another turn; a 4xx fails at once.
    for _ in range(TURN_ATTEMPTS - 1):
        try:
            return await _turn(client=client, text=text)
        except (httpx.TimeoutException, TurnFailedError):
            continue
    return await _turn(client=client, text=text)


async def _turn(client: httpx.AsyncClient, text: str) -> Verdict:
    conversation = await client.post("/api/conversations", json={"title": "guardrail eval"})
    conversation.raise_for_status()
    path = f"/api/conversations/{conversation.json()['id']}"
    try:
        reply = await client.post(f"{path}/messages", json={"content": text})
        if reply.status_code >= 500:
            raise TurnFailedError(reply.text[:200])
        reply.raise_for_status()
        checks = reply.json()["provenance"]["checks"]
    finally:
        await client.delete(path)
    check = next((check for check in checks if check["name"] == CHECK_NAME), None)
    if check is None:
        raise TurnFailedError(f"the reply has no {CHECK_NAME} check")
    return Verdict(category=check["detail"] if check["passed"] else FAILED, language=None)


def report(items: list[GoldItem], verdicts: list[Verdict], scores: dict[str, object]) -> None:
    per_category = scores["per_category"]
    assert isinstance(per_category, dict)
    print(  # noqa: T201
        f"accuracy {scores['accuracy']:.1%} on {len(items)} | false declines "
        f"{scores['false_declines']} | false pointers {scores['false_pointers']} | missed "
        f"{scores['missed']} | harm {scores['harm']} | failed {scores['failed_checks']} | language "
        f"{_percent(value=scores['language_accuracy'])}"
    )
    for category, values in per_category.items():
        print(  # noqa: T201
            f"  {category:15} precision {_percent(value=values['precision']):>6}  recall "
            f"{_percent(value=values['recall']):>6}  n={values['support']}"
        )
    errors = sorted(
        (
            (item.label.value, verdict.category, item)
            for item, verdict in zip(items, verdicts, strict=True)
            if item.label.value != effective(category=verdict.category)
        ),
        key=lambda error: (error[0], error[1], error[2].id),
    )
    for gold, got, item in errors:
        text = " ".join(item.text.split())
        print(f"  {item.id:4} {gold:15} -> {got:15} {text[:90]}")  # noqa: T201


def _percent(value: object) -> str:
    return "-" if value is None else f"{value:.0%}"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["tune", "heldout", "all"], default="tune")
    parser.add_argument(
        "--model", choices=[model.value for model in Model], default=CHECK_MODEL.value
    )
    parser.add_argument("--base-url", help="classify through a running backend instead")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", type=Path, help="write the verdicts and scores as JSON")
    args = parser.parse_args()
    items = [
        item for item in load_gold(path=GOLD_PATH) if args.split in ("all", SPLITS[item.split])
    ]
    if args.base_url is not None:
        settings = EvalSettings()
        async with httpx.AsyncClient(timeout=TURN_TIMEOUT_SECONDS) as bank:
            token = await log_in(bank=bank, customer=settings.evals_username, settings=settings)
        async with httpx.AsyncClient(
            base_url=args.base_url,
            timeout=TURN_TIMEOUT_SECONDS,
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            verdicts = [await classify_via_backend(client=client, text=item.text) for item in items]
    else:
        apertus = ApertusClient(settings=get_settings())
        limit = asyncio.Semaphore(args.concurrency)

        async def classify(text: str) -> Verdict:
            async with limit:
                return await classify_direct(apertus=apertus, model=Model(args.model), text=text)

        try:
            verdicts = await asyncio.gather(*(classify(text=item.text) for item in items))
        finally:
            await apertus.close()
    scores = score(items=items, verdicts=verdicts)
    report(items=items, verdicts=verdicts, scores=scores)
    if args.out is not None:
        args.out.write_text(
            json.dumps(
                {
                    "scores": scores,
                    "verdicts": {
                        item.id: verdict.model_dump()
                        for item, verdict in zip(items, verdicts, strict=True)
                    },
                    "confusion": Counter(
                        f"{item.label.value}->{effective(category=verdict.category)}"
                        for item, verdict in zip(items, verdicts, strict=True)
                    ),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
