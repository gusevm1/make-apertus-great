import json
from typing import Any, Literal

from app.clients.apertus import Message
from app.core.prompts import load_prompts
from app.features.widgets.catalogue.prompts import catalogue_prompt
from evals.widgets.page import preview

PROMPTS = load_prompts(prompts_py=__file__)

Variant = Literal["html_svg", "html_d3", "shapes", "jinja", "catalogue", "catalogue_schema"]
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


def repair_message(error: str) -> Message:
    return Message(role="user", content=PROMPTS["catalogue_repair"].format(error=error))


def _system(variant: Variant) -> Message:
    # Both catalogue variants share one prompt; they differ only in how the call holds the schema.
    key = "catalogue" if variant.startswith("catalogue") else variant
    content = PROMPTS[key].format(rules=PROMPTS["rules"], catalogue=catalogue_prompt())
    return Message(role="system", content=content)


def _generate(task: str, data: dict[str, Any]) -> str:
    shortened = json.dumps(preview(value=data), ensure_ascii=False, indent=1)
    return PROMPTS["generate"].format(request=request(task=task), data=shortened)
