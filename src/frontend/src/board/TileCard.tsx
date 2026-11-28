import { type KeyboardEvent, useEffect, useState } from "react";
import { SmallIcon, TileIcon } from "./icons";
import { pillOf, TileBody } from "./Tiles";
import type { SourceView, Tile } from "./types";

const TITLE_MAX_LENGTH = 80;

export interface TileActions {
  onSelect: (tileId: string | null) => void;
  onMove: (tileId: string, position: number) => void;
  onRename: (tileId: string, title: string) => void;
  onAsk: (tile: Tile) => void;
  onRemove: (tileId: string) => void;
  onSource: (view: SourceView) => void;
}

/** One tile: its heading, what the template draws, and the toolbar once it is selected. */
export function TileCard({
  tile,
  index,
  count,
  isHero,
  isSmall,
  isSelected,
  isGrowing,
  actions,
}: {
  tile: Tile;
  index: number;
  count: number;
  isHero: boolean;
  isSmall: boolean;
  isSelected: boolean;
  isGrowing: boolean;
  actions: TileActions;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [isRemoveArmed, setIsRemoveArmed] = useState(false);
  const [isDropTarget, setIsDropTarget] = useState(false);

  // Leaving the tile ends a rename or an armed remove.
  useEffect(() => {
    if (isSelected) return;
    setDraft(null);
    setIsRemoveArmed(false);
  }, [isSelected]);

  function saveTitle() {
    if (draft === null) return;
    const title = draft.trim().slice(0, TITLE_MAX_LENGTH);
    setDraft(null);
    if (title !== "" && title !== tile.title) actions.onRename(tile.id, title);
  }

  function handleTitleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") saveTitle();
    if (event.key === "Escape") {
      event.stopPropagation();
      setDraft(null);
    }
  }

  function handleRemove() {
    if (!isRemoveArmed) {
      setIsRemoveArmed(true);
      return;
    }
    actions.onRemove(tile.id);
  }

  const classes = ["tile"];
  if (isHero) classes.push("hero");
  if (isSmall) classes.push("small");
  if (isSelected) classes.push("sel");
  if (isGrowing) classes.push("grow");
  if (isDropTarget) classes.push("drop-target");
  const pill = pillOf(tile.payload);

  return (
    <article
      className={classes.join(" ")}
      aria-label={tile.title}
      onClick={(event) => {
        event.stopPropagation();
        actions.onSelect(tile.id);
      }}
      draggable={isSelected && draft === null}
      onDragStart={(event) => {
        event.dataTransfer.setData("text/x-tile", tile.id);
        event.dataTransfer.effectAllowed = "move";
      }}
      onDragOver={(event) => {
        if (!event.dataTransfer.types.includes("text/x-tile")) return;
        event.preventDefault();
        setIsDropTarget(true);
      }}
      onDragLeave={() => setIsDropTarget(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDropTarget(false);
        const movedId = event.dataTransfer.getData("text/x-tile");
        if (movedId !== "" && movedId !== tile.id)
          actions.onMove(movedId, index);
      }}
    >
      {isSelected && (
        <div className="bar" role="toolbar" aria-label={`Tile ${tile.title}`}>
          <button
            type="button"
            aria-label="Move earlier"
            title="Move earlier"
            disabled={index === 0}
            onClick={() => actions.onMove(tile.id, index - 1)}
          >
            <SmallIcon name="earlier" />
          </button>
          <button
            type="button"
            aria-label="Move later"
            title="Move later"
            disabled={index === count - 1}
            onClick={() => actions.onMove(tile.id, index + 1)}
          >
            <SmallIcon name="later" />
          </button>
          <button
            type="button"
            aria-label="Rename"
            title="Rename"
            onClick={() => setDraft(tile.title)}
          >
            <SmallIcon name="rename" />
          </button>
          <button
            type="button"
            aria-label="Ask about this tile"
            title="Ask about this tile"
            onClick={() => actions.onAsk(tile)}
          >
            <SmallIcon name="ask" />
          </button>
          <button
            type="button"
            className={isRemoveArmed ? "danger" : undefined}
            aria-label={isRemoveArmed ? "Click again to remove" : "Remove"}
            title={isRemoveArmed ? "Click again to remove" : "Remove"}
            onClick={handleRemove}
            onBlur={() => setIsRemoveArmed(false)}
          >
            <SmallIcon name="remove" />
            {isRemoveArmed && <span>Remove</span>}
          </button>
        </div>
      )}
      <div className="th">
        <span className="chip">
          <TileIcon template={tile.template} />
        </span>
        {draft === null ? (
          <h2>{tile.title}</h2>
        ) : (
          <input
            className="rename"
            aria-label="Title of the tile"
            value={draft}
            maxLength={TITLE_MAX_LENGTH}
            autoFocus
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleTitleKey}
            onBlur={saveTitle}
          />
        )}
        {pill !== null && <span className="end">{pill}</span>}
      </div>
      <TileBody
        payload={tile.payload}
        isHero={isHero}
        isSmall={isSmall}
        onSource={actions.onSource}
      />
    </article>
  );
}
