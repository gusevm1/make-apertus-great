from pydantic import BaseModel


class Source(BaseModel):
    id: str
    title: str
    url: str | None = None


# A page a tool result comes from. Tools list them under `sources` in their result.
class ResultSource(BaseModel):
    title: str
    url: str


class Check(BaseModel):
    name: str
    passed: bool
    detail: str | None = None


# A record behind a figure, as the page lists it; text, because it is only shown.
class FigureRow(BaseModel):
    id: str
    date: str | None = None
    text: str
    amount_chf: str | None = None


# Where one figure of an answer comes from: the tool result, page or document that holds it.
class FigureSource(BaseModel):
    text: str  # the figure as the answer writes it
    label: str
    tool_call_id: str | None = None
    url: str | None = None
    rows: list[FigureRow] = []
    count: int = 0


class Provenance(BaseModel):
    model: str
    latency_ms: int
    sources: list[Source] = []
    checks: list[Check] = []
    figures: list[FigureSource] = []
