from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.prompts import load_prompts
from app.core.provenance import Provenance

PROMPTS = load_prompts(prompts_py=__file__)


class ToolCall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    message_id: UUID
    position: int
    round: int
    plan: str
    reason: str
    tool_name: str
    title: str
    icon: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    provenance: Provenance | None
    created_at: datetime


class ResponseToolCall(BaseModel):
    id: UUID
    conversation_id: UUID
    message_id: UUID
    position: int
    round: int
    plan: str
    reason: str
    tool_name: str
    title: str
    icon: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    provenance: Provenance | None
    created_at: datetime


class ToolRequest(BaseModel):
    reason: str = Field(description=PROMPTS["request_reason"])
    tool: str = Field(description=PROMPTS["request_tool"])
    arguments: dict[str, Any] = Field(
        default_factory=dict, description=PROMPTS["request_arguments"]
    )


class ToolDecision(BaseModel):
    plan: str = Field(description=PROMPTS["decision_plan"])
    calls: list[ToolRequest] = Field(
        default_factory=list,
        description=PROMPTS["decision_calls"],
    )
