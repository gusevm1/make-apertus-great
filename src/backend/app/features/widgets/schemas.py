from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.prompts import load_prompts
from app.core.provenance import Check

PROMPTS = load_prompts(prompts_py=__file__)
Form = Literal["live", "static"]


class Widget(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    conversation_id: UUID
    title: str
    current_version: int
    dashboard_id: str | None
    dashboard_widget_id: str | None
    published_version: int | None
    created_at: datetime


class WidgetVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    widget_id: UUID
    number: int
    spec: dict[str, Any]
    data: dict[str, Any]
    request: str
    model: str | None
    latency_ms: int
    tool_call_ids: list[str]
    checks: list[Check]
    created_at: datetime


class BuildWidgetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=80, description=PROMPTS["arg_title"])
    request: str = Field(min_length=1, max_length=300, description=PROMPTS["arg_request"])


# What the chat learns about the widget it built; the customer sees the widget on the canvas.
class BuiltWidget(BaseModel):
    widget_id: UUID
    version_number: int
    title: str
    checks: list[Check]


class ResponseWidgetVersion(BaseModel):
    widget_id: UUID
    number: int
    title: str
    html: str
    model: str | None
    latency_ms: int
    checks: list[Check]
    # The version the customer's e-banking dashboard shows, or None.
    published_version: int | None
    created_at: datetime


class RequestWidgetPublicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The dashboard the customer is on (the host's `dashboard_id`); None means the default one.
    dashboard_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class ResponseWidgetPublication(BaseModel):
    widget_id: UUID
    version_number: int
    # Set by every publication; typed like the widget's own columns, which start empty.
    dashboard_id: str | None
    dashboard_widget_id: str | None
