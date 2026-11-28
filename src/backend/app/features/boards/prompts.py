import json
from typing import Any

from app.core.prompts import load_prompts
from app.features.board_plans.schemas import Signal
from app.features.boards.schemas import Tile
from app.features.tiles.schemas import AnyPayload

PROMPTS = load_prompts(prompts_py=__file__)


def board_guide(signals: list[Signal], labels: dict[str, str]) -> str:
    """The board decision's job; `labels` maps a signal id to the tile it is on the board as."""
    lines = "\n".join(_signal(signal=signal, label=labels.get(signal.id)) for signal in signals)
    return PROMPTS["guide"].format(signals=lines or "(none)", catalogue=PROMPTS["catalogue"])


def board_context(
    name: str,
    tiles: list[tuple[str, Tile, AnyPayload | None, str]],
    selected: tuple[str, Tile, AnyPayload] | None,
    signals: list[Signal],
) -> str:
    """The open board as the customer's message carries it."""
    lines = "\n".join(
        _tile(label=label, tile=tile, payload=payload, meaning=meaning)
        for label, tile, payload, meaning in tiles
    )
    selected_text = ""
    if selected is not None:
        label, tile, payload = selected
        selected_text = PROMPTS["context_selected"].format(
            label=label, title=_escaped(text=tile.title), payload=_json(value=figures(payload))
        )
    return PROMPTS["context"].format(
        name=_escaped(text=name),
        tiles=lines or PROMPTS["context_empty"],
        selected=selected_text,
        findings="\n".join(f"- {_escaped(text=signal.text)}" for signal in signals),
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
    return PROMPTS["context_tile"].format(
        label=label,
        title=title,
        template=tile.template,
        figure=payload.figure_chf,
        meaning=_escaped(text=meaning),
    )


def _json(value: Any) -> str:
    return _escaped(text=json.dumps(value, ensure_ascii=False))


def _escaped(text: str) -> str:
    # Escaped, a text can neither close its block nor open a tag of its own.
    return text.replace("<", "&lt;").replace(">", "&gt;")
