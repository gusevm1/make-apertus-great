import json
from typing import Any

from app.core.prompts import load_prompts
from app.features.widgets.catalogue.schemas import COMPONENTS, FIELD_PATTERN, PATH_PATTERN

PROMPTS: dict[str, Any] = load_prompts(prompts_py=__file__)
_KINDS = {
    PATH_PATTERN: "path into DATA",
    FIELD_PATTERN: "field name of the rows",
}


def catalogue_prompt() -> str:
    """The catalogue as Apertus reads it: fields come from the models, words from prompts.yaml."""
    parts = [PROMPTS["intro"].strip()]
    for component in COMPONENTS:
        schema = component.model_json_schema()
        # Recursive models (stack, grid) put their own schema under $defs.
        schema = schema["$defs"][component.__name__] if "$ref" in schema else schema
        name = schema["properties"]["type"]["const"]
        required = set(schema.get("required", []))
        fields = "; ".join(
            f"{field} ({_kind(prop=prop)}{'' if field in required else ', optional'})"
            for field, prop in schema["properties"].items()
            if field != "type"
        )
        parts.append(
            f"{name}: {PROMPTS[name]['description']}\n"
            f"  fields: {fields}\n"
            f"  example: {json.dumps(PROMPTS[name]['example'], ensure_ascii=False)}"
        )
    return "\n\n".join(parts)


def _kind(prop: dict[str, Any]) -> str:
    options = [option for option in prop.get("anyOf", [prop]) if option.get("type") != "null"]
    option = options[0]
    if option.get("pattern") in _KINDS:
        return _KINDS[option["pattern"]]
    if option.get("type") == "array":
        items = option["items"]
        if items.get("pattern") == FIELD_PATTERN:
            return "list of field names of the rows"
        if "$ref" in items and items["$ref"].endswith("/Stat"):
            return "list of {label, value: path into DATA}"
        return "list of components"
    if "enum" in option:
        return "one of " + ", ".join(str(value) for value in option["enum"])
    if option.get("type") == "boolean":
        return "true or false"
    return "text"
