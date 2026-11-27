from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.core.prompts import load_prompts
from app.core.provenance import Provenance
from app.core.tools import Tool

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


class RequestToolCallConfirmationCreate(BaseModel):
    is_allowed: bool


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


def decision_schema(tools: list[Tool[Any]]) -> type[ToolDecision]:
    """`ToolDecision` whose JSON schema names only these tools, so the model cannot invent one."""
    # The empty name stays allowed: the model writes it for "no call", and the loop skips it.
    names: list[JsonValue] = [*(tool.name for tool in tools), ""]

    class NamedToolRequest(ToolRequest):
        tool: str = Field(description=PROMPTS["request_tool"], json_schema_extra={"enum": names})

    class NamedToolDecision(ToolDecision):
        calls: list[NamedToolRequest] = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
            default_factory=list, description=PROMPTS["decision_calls"]
        )

    return NamedToolDecision
