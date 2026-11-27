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


class Provenance(BaseModel):
    model: str
    latency_ms: int
    sources: list[Source] = []
    checks: list[Check] = []
