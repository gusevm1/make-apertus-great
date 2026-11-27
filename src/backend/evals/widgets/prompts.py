import json
from typing import Any, Literal

from app.clients.apertus import Message
from app.core.prompts import load_prompts
from evals.widgets.page import preview

PROMPTS = load_prompts(prompts_py=__file__)

Variant = Literal["html_svg", "html_d3", "shapes", "jinja"]
Mode = Literal["rewrite", "edits"]
TASKS = [name.removeprefix("task_") for name in PROMPTS if name.startswith("task_")]
REVISIONS = [name.removeprefix("revision_") for name in PROMPTS if name.startswith("revision_")]


def request(task: str) -> str:
    return PROMPTS[f"task_{task}"]


def change(revision: str) -> str:
    return PROMPTS[f"revision_{revision}"]


def generate_messages(variant: Variant, task: str, data: dict[str, Any]) -> list[Message]:
    return [_system(variant=variant), Message(role="user", content=_generate(task=task, data=data))]


def revise_messages(
    variant: Variant, mode: Mode, task: str, data: dict[str, Any], code: str, revision: str
) -> list[Message]:
    content = PROMPTS[f"revise_{mode}"].format(
        generate=_generate(task=task, data=data), code=code, change=change(revision=revision)
    )
    return [_system(variant=variant), Message(role="user", content=content)]


def _system(variant: Variant) -> Message:
    return Message(role="system", content=PROMPTS[variant].format(rules=PROMPTS["rules"]))


def _generate(task: str, data: dict[str, Any]) -> str:
    shortened = json.dumps(preview(value=data), ensure_ascii=False, indent=1)
    return PROMPTS["generate"].format(request=request(task=task), data=shortened)
