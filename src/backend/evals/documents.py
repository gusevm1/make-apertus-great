"""Live document eval: uploads each sample PDF and scores the kind and fields Apertus read."""

import argparse
import asyncio
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from pydantic import BaseModel, Field

from evals.run import EvalSettings

DOCUMENTS_PATH = Path(__file__).with_name("documents.yaml")
SAMPLES_DIR = Path(__file__).parents[3] / "starter/resources/Demodaten/Dokumente"
# Longer than the proxy's 300 s: the eval calls the backend directly and waits out a slow gateway.
UPLOAD_TIMEOUT_SECONDS = 600

Value = float | date | str
Verdict = Literal["right", "wrong", "missing"]


class Login(BaseModel):
    username: str
    password: str


class ExpectedDocument(BaseModel):
    file: str
    kind: str
    # Each field accepts one value or any of a list.
    fields: dict[str, Value | list[Value]] = Field(default_factory=dict)


class Catalogue(BaseModel):
    customers: dict[str, Login]
    documents: list[ExpectedDocument]


class FieldScore(BaseModel):
    name: str
    verdict: Verdict
    got: str | None = None


def load_catalogue(path: Path) -> Catalogue:
    return Catalogue.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _value_matches(expected: Value, field: dict[str, Any]) -> bool:
    if isinstance(expected, date):
        return field.get("date") == expected.isoformat()
    if isinstance(expected, str):
        text = field.get("text")
        return text is not None and _squeezed(text=expected) in _squeezed(text=text)
    amount = field.get("amount")
    return amount is not None and abs(float(amount) - expected) < 0.005


def _shown(field: dict[str, Any]) -> str:
    values = [field.get(key) for key in ("amount", "date", "text")]
    return " / ".join(str(value) for value in values if value is not None) or "no value"


def score_fields(expected: ExpectedDocument, response: dict[str, Any]) -> list[FieldScore]:
    got = {field["name"]: field for field in response.get("fields", [])}
    scores = []
    for name, accepted in expected.fields.items():
        field = got.get(name)
        if field is None:
            scores.append(FieldScore(name=name, verdict="missing"))
            continue
        values = accepted if isinstance(accepted, list) else [accepted]
        is_right = any(_value_matches(expected=value, field=field) for value in values)
        verdict: Verdict = "right" if is_right else "wrong"
        scores.append(FieldScore(name=name, verdict=verdict, got=_shown(field=field)))
    return scores


def _checks(response: dict[str, Any]) -> list[dict[str, Any]]:
    return (response.get("provenance") or {}).get("checks", [])


def _check_detail(response: dict[str, Any]) -> str:
    return " ".join(check.get("detail") or "" for check in _checks(response=response))


def describe_line(
    expected: ExpectedDocument, response: dict[str, Any], scores: list[FieldScore]
) -> str:
    kind = response.get("kind")
    kind_part = (
        "kind right" if kind == expected.kind else f"kind WRONG ({kind}, not {expected.kind})"
    )
    parts = [kind_part]
    for check in _checks(response=response):
        if check.get("name") == "described" and check.get("passed") is False:
            parts.append(f"NOT DESCRIBED ({check['detail']})")
    for score in scores:
        if score.verdict == "right":
            parts.append(f"{score.name} right")
        elif score.verdict == "wrong":
            parts.append(f"{score.name} WRONG ({score.got})")
        elif f"dropped {score.name}:" in _check_detail(response=response):
            parts.append(f"{score.name} MISSING (dropped by fields_in_text)")
        else:
            parts.append(f"{score.name} MISSING")
    return f"{Path(expected.file).name[:55]:55}  " + ", ".join(parts)


async def _token(bank: httpx.AsyncClient, login: Login) -> str:
    response = await bank.post("/auth/login", json=login.model_dump())
    response.raise_for_status()
    return response.json()["token"]


async def upload(client: httpx.AsyncClient, token: str, path: Path) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/api/documents",
        headers=headers,
        files={"file": (path.name, await asyncio.to_thread(path.read_bytes), "application/pdf")},
    )
    response.raise_for_status()
    document = response.json()
    # The run leaves nothing behind in the demo accounts.
    deleted = await client.delete(f"/api/documents/{document['id']}", headers=headers)
    deleted.raise_for_status()
    return document


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=EvalSettings().evals_base_url)
    args = parser.parse_args()
    if args.base_url is None:
        parser.error("set EVALS_BASE_URL or pass --base-url http://localhost:<your backend port>")
    catalogue = load_catalogue(path=DOCUMENTS_PATH)
    kinds_right = 0
    failed_uploads = 0
    verdicts: Counter[str] = Counter()
    async with (
        httpx.AsyncClient(
            base_url=EvalSettings().banking_api_url, timeout=UPLOAD_TIMEOUT_SECONDS
        ) as bank,
        httpx.AsyncClient(base_url=args.base_url, timeout=UPLOAD_TIMEOUT_SECONDS) as client,
    ):
        # ponytail: one upload after the other, gentle on the prepaid Apertus credit
        for expected in catalogue.documents:
            login = catalogue.customers[Path(expected.file).parts[0]]
            try:
                token = await _token(bank=bank, login=login)
                response = await upload(
                    client=client, token=token, path=SAMPLES_DIR / expected.file
                )
            except httpx.HTTPError as error:
                # Not the model's miss: kept out of the scores.
                failed_uploads += 1
                print(f"{expected.file}: upload failed: {error!r}")  # noqa: T201
                continue
            kinds_right += response.get("kind") == expected.kind
            scores = score_fields(expected=expected, response=response)
            verdicts.update(score.verdict for score in scores)
            line = describe_line(expected=expected, response=response, scores=scores)
            print(line, flush=True)  # noqa: T201
    total_fields = sum(verdicts.values())
    scored = len(catalogue.documents) - failed_uploads
    print(f"kinds: {kinds_right} of {scored} right, {failed_uploads} uploads failed")  # noqa: T201
    print(  # noqa: T201
        f"fields: {verdicts['right']} of {total_fields} right, "
        f"{verdicts['wrong']} wrong, {verdicts['missing']} missing"
    )
    # A score, not a gate.
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
