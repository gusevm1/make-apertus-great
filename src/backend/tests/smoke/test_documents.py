from uuid import uuid4

import httpx2

from tests.conftest import OCR_MARKDOWN, FakeApertus

PDF = {"file": ("Lohnabrechnung.pdf", b"%PDF-1.7 fake", "application/pdf")}


async def test_uploaded_document_is_read_once_and_reaches_the_prompt(
    client: httpx2.AsyncClient, apertus: FakeApertus
) -> None:
    uploaded = await client.post("/api/documents", files=PDF)
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert document["name"] == "Lohnabrechnung.pdf"
    assert "markdown" not in document

    listed = await client.get("/api/documents")
    assert [item["id"] for item in listed.json()] == [document["id"]]

    conversation = (await client.post("/api/conversations", json={})).json()
    url = f"/api/conversations/{conversation['id']}/messages"
    reply = await client.post(
        url, json={"content": "What is my net salary?", "document_ids": [document["id"]]}
    )

    assert reply.status_code == 201
    question = apertus.requests[-1]["messages"][1]["content"]
    assert '<document name="Lohnabrechnung.pdf">' in question
    assert OCR_MARKDOWN in question
    assert question.endswith("What is my net salary?")
    stored_question, _ = (await client.get(url)).json()
    assert stored_question["content"] == "What is my net salary?"
    assert stored_question["documents"] == [{"id": document["id"], "name": "Lohnabrechnung.pdf"}]


async def test_an_unknown_document_is_not_found(
    client: httpx2.AsyncClient,
) -> None:
    conversation = (await client.post("/api/conversations", json={})).json()

    reply = await client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Hi", "document_ids": [str(uuid4())]},
    )

    assert reply.status_code == 404


async def test_an_empty_upload_is_refused(client: httpx2.AsyncClient) -> None:
    empty = await client.post("/api/documents", files={"file": ("a.pdf", b"", "application/pdf")})

    assert empty.status_code == 400
