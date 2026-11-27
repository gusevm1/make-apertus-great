import json
from typing import Any

from app.clients.apertus import Message
from app.core.prompts import load_prompts
from app.features.widgets.catalogue.prompts import catalogue_prompt
from app.features.widgets.catalogue.schemas import WidgetSpec

PROMPTS = load_prompts(prompts_py=__file__)
PREVIEW_ROWS = 20
PREVIEW_IDS = 3


def spec_messages(request: str, data: dict[str, Any]) -> list[Message]:
    user = PROMPTS["spec_user"].format(
        request=request,
        rows=PREVIEW_ROWS,
        ids=PREVIEW_IDS,
        data=json.dumps(_preview(value=data), ensure_ascii=False, indent=1),
    )
    return [
        Message(role="system", content=PROMPTS["spec_system"].format(catalogue=catalogue_prompt())),
        Message(role="user", content=user),
    ]


def repair_messages(messages: list[Message], spec: WidgetSpec, error: str) -> list[Message]:
    return [
        *messages,
        Message(role="assistant", content=spec.model_dump_json(exclude_none=True)),
        Message(role="user", content=PROMPTS["spec_repair"].format(error=error)),
    ]


def _preview(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {name: _preview(value=item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        limit = PREVIEW_IDS if key.endswith("ids") else PREVIEW_ROWS
        return [_preview(value=item) for item in value[:limit]]
    return value
