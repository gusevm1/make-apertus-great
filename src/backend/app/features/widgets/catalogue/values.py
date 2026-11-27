import re
from typing import Any

from app.core.errors import BadRequestError

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_SEGMENT = re.compile(r"([A-Za-z_]\w*)(?:\[(\d+)\])?")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")


def resolve(path: str, data: dict[str, Any]) -> Any:
    """The value at a path such as "months[5].total_chf"; the error names what exists instead."""
    value: Any = data
    walked = ""
    for match in _SEGMENT.finditer(path):
        name, index = match.group(1), match.group(2)
        if not isinstance(value, dict) or name not in value:
            fields = ", ".join(value) if isinstance(value, dict) else "none, it is not an object"
            where = "DATA" if walked == "" else walked
            raise BadRequestError(f"{path}: {where} has no field {name}; fields: {fields}")
        value = value[name]
        walked = name if walked == "" else f"{walked}.{name}"
        if index is None:
            continue
        if not isinstance(value, list) or int(index) >= len(value):
            size = len(value) if isinstance(value, list) else 0
            raise BadRequestError(f"{path}: {walked} has {size} items, no index {index}")
        value = value[int(index)]
        walked = f"{walked}[{index}]"
    return value


def rows(path: str, data: dict[str, Any], fields: list[str]) -> list[dict[str, Any]]:
    """The list at a path, checked to hold objects with every named field."""
    found = resolve(path=path, data=data)
    if not isinstance(found, list) or not all(isinstance(row, dict) for row in found):
        raise BadRequestError(f"{path} is not a list of rows")
    for index, row in enumerate(found):
        for field in fields:
            if field not in row:
                raise BadRequestError(
                    f"{path}[{index}] has no field {field}; fields: {', '.join(row)}"
                )
    return found


def last_field(path: str) -> str:
    return _SEGMENT.findall(path)[-1][0]


def booking_ids(path: str, data: dict[str, Any]) -> list[str]:
    """The booking ids of the row a figure sits in: months[5]'s for months[5].total_chf."""
    parent = path.rpartition(".")[0]
    if parent == "":
        return []
    row = resolve(path=parent, data=data)
    if not isinstance(row, dict) or not isinstance(row.get("booking_ids"), list):
        return []
    return row["booking_ids"]


def number(value: Any, decimals: int = 2) -> str:
    """8034.42 → "8'034.42", as the e-banking writes it."""
    fixed = f"{abs(value):,.{decimals}f}".replace(",", "'")
    return f"-{fixed}" if value < 0 and float(fixed.replace("'", "")) != 0 else fixed


def display(field: str, value: Any) -> str:
    """A value as text, formatted by its field name and shape."""
    if value is None:
        return "–"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int | float):
        if field.endswith("_chf"):
            return f"CHF {number(value=value)}"
        return number(value=value, decimals=0 if float(value).is_integer() else 2)
    text = str(value)
    date = _DATE.match(text)
    if date is not None:
        return f"{date.group(3)}.{date.group(2)}.{date.group(1)}"
    month = _MONTH.match(text)
    if month is not None:
        return f"{MONTHS[int(month.group(2)) - 1]} {month.group(1)}"
    return text


def short(field: str, value: Any) -> str:
    """An axis label: "2026-05", or "05" in a field named month, → "May"."""
    text = str(value)
    month = _MONTH.match(text)
    if month is not None:
        return MONTHS[int(month.group(2)) - 1]
    if field == "month" and text.isdigit() and 1 <= int(text) <= 12:
        return MONTHS[int(text) - 1]
    return display(field=field, value=value)
