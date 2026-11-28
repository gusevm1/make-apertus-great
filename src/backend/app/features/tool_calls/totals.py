"""The totals of a tool result in one server-written sentence, so the answer never adds rows up."""

from datetime import date
from decimal import Decimal
from typing import Any

from app.features.tool_calls.prompts import PROMPTS

GROUPS_LISTED = 6


def total_sentence(result: dict[str, Any], arguments: dict[str, Any]) -> str | None:
    """The sentence for a result that carries a sum, or None when it carries none."""
    period = _period(date_from=arguments.get("date_from"), date_to=arguments.get("date_to"))
    if "money_out_change_chf" in result:
        return " ".join(
            _moved(result=result[part], period=_period_of(part=result[part]))
            for part in ("earlier", "later")
        )
    if "spent_chf" in result:
        groups = ", ".join(
            PROMPTS["total_group"].format(
                group=group["group"], amount=_chf(value=group["spent_chf"])
            )
            for group in result.get("groups", [])[:GROUPS_LISTED]
        )
        sentence = PROMPTS["total_spent"].format(
            amount=_chf(value=result["spent_chf"]), count=result["count"], period=period
        )
        return (
            sentence
            if groups == ""
            else f"{sentence} {PROMPTS['total_groups'].format(groups=groups)}"
        )
    if "money_out_chf" in result and "count" in result:
        sentence = _moved(result=result, period=period)
        if "average_out_chf" in result:
            sentence += " " + PROMPTS["total_average"].format(
                amount=_chf(value=result["average_out_chf"])
            )
        return sentence
    if "total_chf" in result and isinstance(result.get("items"), list):
        return PROMPTS["total_due"].format(
            amount=_chf(value=result["total_chf"]), count=len(result["items"]), period=period
        )
    if "sum_chf" in result and "total" in result:
        return PROMPTS["total_payments"].format(
            amount=_chf(value=result["sum_chf"]), count=result["total"], period=period
        )
    return None


def _moved(result: dict[str, Any], period: str) -> str:
    out, money_in = _chf(value=result["money_out_chf"]), _chf(value=result["money_in_chf"])
    if Decimal(str(result["money_in_chf"])) == 0:
        return PROMPTS["total_out"].format(amount=out, count=result["count"], period=period)
    if Decimal(str(result["money_out_chf"])) == 0:
        return PROMPTS["total_in"].format(amount=money_in, count=result["count"], period=period)
    return PROMPTS["total_out_and_in"].format(
        out=out, money_in=money_in, count=result["count"], period=period
    )


def _period_of(part: dict[str, Any]) -> str:
    return _period(date_from=part.get("date_from"), date_to=part.get("date_to"))


def _period(date_from: Any, date_to: Any) -> str:
    if date_from is None and date_to is None:
        return PROMPTS["total_whole_ledger"]
    if date_to is None:
        return PROMPTS["total_since"].format(date_from=_day(value=date_from))
    if date_from is None:
        return PROMPTS["total_until"].format(date_to=_day(value=date_to))
    return PROMPTS["total_between"].format(
        date_from=_day(value=date_from), date_to=_day(value=date_to)
    )


def _day(value: Any) -> str:
    day = date.fromisoformat(str(value)[:10])
    return f"{day.day:02d}.{day.month:02d}.{day.year}"


def _chf(value: Any) -> str:
    return f"CHF {abs(Decimal(str(value))):,.2f}".replace(",", "'")
