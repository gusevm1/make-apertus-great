from pydantic import BaseModel

from app.core.provenance import ResultSource


class WebPage(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearch(BaseModel):
    results: list[WebPage]
    sources: list[ResultSource]
