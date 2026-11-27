from pydantic import BaseModel

from app.core.provenance import ResultSource


class WebPage(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearch(BaseModel):
    # The model sees a call's result, not its arguments, and the customer may have changed them.
    query: str
    results: list[WebPage]
    sources: list[ResultSource]
