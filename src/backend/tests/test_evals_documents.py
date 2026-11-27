from datetime import date

import httpx

from evals.documents import (
    DOCUMENTS_PATH,
    SAMPLES_DIR,
    ExpectedDocument,
    describe_line,
    load_catalogue,
    score_fields,
    upload,
)

REMINDER = ExpectedDocument(
    file="P3_Daniela_Ruegg/Mahnung_Zahnarzt_Lina_Daniela_Rueegg.pdf",
    kind="reminder",
    fields={
        "amount_due": 440.0,
        "due_date": date(2026, 11, 30),
        "iban": "CH97 3088 8000 0123 4567 8",
        "payee": ["Zahnarztpraxis Neuwiesen", "Dr. Andrea Vogt"],
    },
)


DOCUMENT_ID = "6f1d3c1e-0000-4000-8000-000000000086"
requests: list[str] = []


def fake_backend(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer token-daniela"
    requests.append(f"{request.method} {request.url.path}")
    if request.method == "DELETE":
        return httpx.Response(204)
    fields = [
        {"name": "amount_due", "amount": 420.0, "passage": "Rechnungsbetrag 420.00"},
        {"name": "due_date", "date": "2026-11-30", "passage": "bis 30.11.2026"},
        {"name": "iban", "text": "CH9730888000012345678", "passage": "CH97 3088 8000 0123 4567 8"},
    ]
    checks = [{"name": "fields_in_text", "detail": 'dropped payee: "Zahlbar an": not in text'}]
    body = {
        "id": DOCUMENT_ID,
        "kind": "reminder",
        "fields": fields,
        "provenance": {"checks": checks},
    }
    return httpx.Response(201, json=body)


async def test_scores_right_wrong_and_missing_fields_of_a_faked_backend() -> None:
    transport = httpx.MockTransport(fake_backend)
    async with httpx.AsyncClient(transport=transport, base_url="http://backend") as client:
        response = await upload(
            client=client, token="token-daniela", path=SAMPLES_DIR / REMINDER.file
        )
    scores = score_fields(expected=REMINDER, response=response)
    verdicts = {score.name: score.verdict for score in scores}
    assert verdicts == {
        "amount_due": "wrong",
        "due_date": "right",
        "iban": "right",
        "payee": "missing",
    }
    line = describe_line(expected=REMINDER, response=response, scores=scores)
    assert "payee MISSING (dropped by fields_in_text)" in line
    assert requests == ["POST /api/documents", f"DELETE /api/documents/{DOCUMENT_ID}"]


def test_an_undescribed_document_prints_the_reason() -> None:
    check = {"name": "described", "passed": False, "detail": "Apertus timed out"}
    response = {"kind": None, "fields": [], "provenance": {"checks": [check]}}
    scores = score_fields(expected=REMINDER, response=response)

    line = describe_line(expected=REMINDER, response=response, scores=scores)

    assert "NOT DESCRIBED (Apertus timed out)" in line


def test_catalogue_names_all_13_pdfs_with_a_login_each() -> None:
    catalogue = load_catalogue(path=DOCUMENTS_PATH)
    assert len(catalogue.documents) == 13
    for document in catalogue.documents:
        assert (SAMPLES_DIR / document.file).is_file()
        assert document.file.split("/")[0] in catalogue.customers
    reminder = next(document for document in catalogue.documents if document.kind == "reminder")
    assert reminder.fields["due_date"] == date(2026, 11, 30)
    assert reminder.fields["amount_due"] == 440.0
