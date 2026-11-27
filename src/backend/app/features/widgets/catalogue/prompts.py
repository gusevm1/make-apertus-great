import json
from typing import Any

from app.core.prompts import load_prompts
from app.features.widgets.catalogue.schemas import COMPONENTS, FIELD_PATTERN, PATH_PATTERN

PROMPTS: dict[str, Any] = load_prompts(prompts_py=__file__)
# Entries of prompts.yaml that are not a component.
NOT_COMPONENTS = {"intro", "component", "field", "optional", "limits", "field_separator", "kinds"}


def catalogue_prompt() -> str:
    """The catalogue as Apertus reads it: fields come from the models, words from prompts.yaml."""
    parts = [PROMPTS["intro"].strip()]
    for component in COMPONENTS:
        schema = component.model_json_schema()
        # Recursive models (stack, grid) put their own schema under $defs.
        schema = schema["$defs"][component.__name__] if "$ref" in schema else schema
        name = schema["properties"]["type"]["const"]
        required = set(schema.get("required", []))
        fields = [
            PROMPTS["field"].format(
                field=field,
                kind=_kind_text(prop=prop),
                limits=_limits(prop=prop),
                optional="" if field in required else PROMPTS["optional"],
            )
            for field, prop in schema["properties"].items()
            if field != "type"
        ]
        parts.append(
            PROMPTS["component"].format(
                name=name,
                description=PROMPTS[name]["description"],
                fields=PROMPTS["field_separator"].join(fields),
                example=json.dumps(PROMPTS[name]["example"], ensure_ascii=False),
            )
        )
    return "\n\n".join(parts)


def _kind_text(prop: dict[str, Any]) -> str:
    option = _option(prop=prop)
    values = ", ".join(str(value) for value in option.get("enum", []))
    return PROMPTS["kinds"][_kind(option=option)].format(values=values)


def _limits(prop: dict[str, Any]) -> str:
    option = _option(prop=prop)
    limits = PROMPTS["limits"]
    if "minItems" in option and "maxItems" in option:
        return limits["items"].format(min=option["minItems"], max=option["maxItems"])
    if "maxItems" in option:
        return limits["at_most_items"].format(max=option["maxItems"])
    if "maxLength" in option:
        return limits["at_most_characters"].format(max=option["maxLength"])
    return ""


def _option(prop: dict[str, Any]) -> dict[str, Any]:
    """The field's schema without its null option."""
    return next(option for option in prop.get("anyOf", [prop]) if option.get("type") != "null")


def _kind(option: dict[str, Any]) -> str:
    if option.get("pattern") == PATH_PATTERN:
        return "path"
    if option.get("pattern") == FIELD_PATTERN:
        return "field"
    if option.get("$ref", "").endswith("/Trend"):
        return "trend"
    if option.get("type") == "array":
        items = option["items"]
        if items.get("pattern") == FIELD_PATTERN:
            return "fields"
        if items.get("$ref", "").endswith("/Stat"):
            return "stats"
        return "components"
    if "enum" in option:
        return "choice"
    if option.get("type") == "boolean":
        return "boolean"
    return "text"
