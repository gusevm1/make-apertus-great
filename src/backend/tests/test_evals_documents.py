from datetime import date

import httpx

from evals.documents import (
    DOCUMENTS_PATH,
    SAMPLES_DIR,
    ExpectedDocument,
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


def fake_backend(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer token-daniela"
    fields = [
        {"name": "amount_due", "amount": 420.0, "passage": "Rechnungsbetrag 420.00"},
        {"name": "due_date", "date": "2026-11-30", "passage": "bis 30.11.2026"},
        {"name": "iban", "text": "CH9730888000012345678", "passage": "CH97 3088 8000 0123 4567 8"},
    ]
    return httpx.Response(201, json={"kind": "reminder", "fields": fields})


async def test_scores_right_wrong_and_missing_fields_of_a_faked_backend() -> None:
    transport = httpx.MockTransport(fake_backend)
    async with httpx.AsyncClient(transport=transport, base_url="http://backend") as client:
        response = await upload(
            client=client, token="token-daniela", path=SAMPLES_DIR / REMINDER.file
        )
    verdicts = {
        score.name: score.verdict for score in score_fields(expected=REMINDER, response=response)
    }
    assert verdicts == {
        "amount_due": "wrong",
        "due_date": "right",
        "iban": "right",
        "payee": "missing",
    }


def test_catalogue_names_all_13_pdfs_with_a_login_each() -> None:
    catalogue = load_catalogue(path=DOCUMENTS_PATH)
    assert len(catalogue.documents) == 13
    for document in catalogue.documents:
        assert (SAMPLES_DIR / document.file).is_file()
        assert document.file.split("/")[0] in catalogue.customers
    reminder = next(document for document in catalogue.documents if document.kind == "reminder")
    assert reminder.fields["due_date"] == date(2026, 11, 30)
    assert reminder.fields["amount_due"] == 440.0
