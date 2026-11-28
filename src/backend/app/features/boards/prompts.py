import json
from typing import Any

from app.core.prompts import load_prompts
from app.features.board_plans.schemas import Signal
from app.features.boards.schemas import Tile
from app.features.tiles.schemas import AnyPayload

PROMPTS = load_prompts(prompts_py=__file__)
SAVED_LISTED = 8


def board_guide(
    signals: list[Signal], labels: dict[str, str], notes: list[str], saved: list[str], payees: str
) -> str:
    """The board decision's job; `labels` maps a signal id to the tile it is on the board as."""
    lines = "\n".join(_signal(signal=signal, label=labels.get(signal.id)) for signal in signals)
    return PROMPTS["guide"].format(
        signals=lines or "(none)",
        notes="\n".join(f"- {note}" for note in notes) or "(none)",
        payees=_escaped(text=payees) or "(none)",
        saved="\n".join(f"- {_escaped(text=note)}" for note in saved[:SAVED_LISTED]) or "(none)",
        catalogue=PROMPTS["catalogue"],
    )


def board_context(
    name: str,
    tiles: list[tuple[str, Tile, AnyPayload | None, str]],
    selected: tuple[str, Tile, AnyPayload, str] | None,
    signals: list[Signal],
) -> str:
    """The open board as the customer's message carries it."""
    # With a tile selected, the others are named only, so the answer stays on that tile.
    lines = "\n".join(
        _tile(label=label, tile=tile, payload=payload, meaning=meaning if selected is None else "")
        for label, tile, payload, meaning in tiles
    )
    selected_text = ""
    if selected is not None:
        label, tile, payload, meaning = selected
        selected_text = PROMPTS["context_selected"].format(
            label=label,
            title=_escaped(text=tile.title),
            meaning=_escaped(text=meaning),
            payload=_json(value=figures(payload)),
        )
    return PROMPTS["context"].format(
        name=_escaped(text=name),
        tiles=lines or PROMPTS["context_empty"],
        selected=selected_text,
        findings="\n".join(f"- {_escaped(text=signal.text)}" for signal in signals)
        if selected is None
        else PROMPTS["context_findings_left_out"],
    )


def figures(payload: AnyPayload) -> dict[str, Any]:
    """What a tile shows, without the rows behind it."""
    return payload.model_dump(mode="json", exclude={"source"})


def _signal(signal: Signal, label: str | None) -> str:
    line = PROMPTS["signal"].format(id=signal.id, text=signal.text)
    if signal.template is not None:
        line += PROMPTS["signal_tile"].format(
            template=signal.template, args=json.dumps(signal.args, ensure_ascii=False)
        )
    if label is not None:
        line += PROMPTS["signal_on_board"].format(label=label)
    return line


def _tile(label: str, tile: Tile, payload: AnyPayload | None, meaning: str) -> str:
    title = _escaped(text=tile.title)
    if payload is None:
        return PROMPTS["context_dropped"].format(label=label, title=title, template=tile.template)
    if meaning == "":
        return PROMPTS["context_tile_named"].format(
            label=label, title=title, template=tile.template
        )
    return PROMPTS["context_tile"].format(
        label=label,
        title=title,
        template=tile.template,
        meaning=_escaped(text=meaning),
    )


def _json(value: Any) -> str:
    return _escaped(text=json.dumps(value, ensure_ascii=False))


def _escaped(text: str) -> str:
    # Escaped, a text can neither close its block nor open a tag of its own.
    return text.replace("<", "&lt;").replace(">", "&gt;")


def payee_lines(facts: str) -> str:
    """The digest's lists of the largest payees, with their headings, from its facts text."""
    lines: list[str] = []
    in_list = False
    for line in facts.splitlines():
        if line.startswith("Largest payees"):
            in_list = True
            lines.append(line)
        elif in_list and line.startswith("- "):
            lines.append(f"  {line}")
        else:
            in_list = False
    return "\n".join(lines)


def payee_names(facts: str, period: str) -> set[str]:
    """The payees the digest lists for a period, such as this_month, in lower case."""
    names: set[str] = set()
    in_period = False
    for line in facts.splitlines():
        if line.startswith("Largest payees"):
            in_period = f"period {period} " in line
        elif in_period and line.startswith("- "):
            names.add(line[2:].rsplit(":", 1)[0].casefold())
        else:
            in_period = False
    return names
