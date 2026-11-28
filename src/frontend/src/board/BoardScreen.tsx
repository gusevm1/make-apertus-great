import { useEffect, useRef, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "../api";
import { sendToHost, useHostContext } from "../host";
import { columnsOf, isSmall, type Unit } from "./layout";
import { SourceDrawer } from "./SourceDrawer";
import { type TileActions, TileCard } from "./TileCard";
import type { Board, SourceView, Tile, TilePublication } from "./types";

function patch(body: unknown): RequestInit {
  return {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/** The open board: its tiles in two columns, the toolbar actions and the source drawer. */
export function BoardScreen({
  token,
  boardId,
  boardName,
  refreshKey,
  onAsk,
  onTilesChanged,
}: {
  token: string;
  boardId: string;
  boardName: string;
  /** Bumped when the chat changed the board; the board is fetched again. */
  refreshKey: number;
  onAsk: (tile: Tile) => void;
  onTilesChanged: (tiles: Tile[]) => void;
}) {
  // The dashboard the customer is on, if any; a published tile goes there.
  const dashboardId = useHostContext()?.dashboard_id ?? null;
  const [board, setBoard] = useState<Board | null>(null);
  const [loadError, setLoadError] = useState<RequestError | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sourceView, setSourceView] = useState<SourceView | null>(null);
  // Only the newest fetch may draw, so a slow one never overwrites a later change.
  const request = useRef(0);

  async function load() {
    const current = ++request.current;
    setLoadError(null);
    try {
      const loaded = await api<Board>(`/api/boards/${boardId}`, token);
      if (current !== request.current) return;
      setBoard(loaded);
      onTilesChanged(loaded.tiles);
    } catch (error) {
      if (current === request.current) setLoadError(requestErrorOf(error));
    }
  }

  // Runs per board and whenever the chat changed it; the token only changes with the customer.
  useEffect(() => {
    void load();
  }, [boardId, refreshKey]);

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedId(null);
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  function showTiles(tiles: Tile[]) {
    setBoard((current) => (current === null ? current : { ...current, tiles }));
    onTilesChanged(tiles);
  }

  async function change(what: string, send: () => Promise<unknown>) {
    setActionError(null);
    try {
      await send();
    } catch (error) {
      setActionError(`${what} did not work. ${requestErrorOf(error).message}`);
    }
    await load();
  }

  if (loadError !== null && board === null) {
    return (
      <div className="state" role="alert">
        <h1>{boardName} did not open</h1>
        <p>{loadError.message}</p>
        <button type="button" className="button go" onClick={() => void load()}>
          Try again
        </button>
      </div>
    );
  }
  if (board === null) {
    return (
      <div className="state" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Opening {boardName}, with today's figures from your accounts…</p>
      </div>
    );
  }

  const tiles = board.tiles;
  const actions: TileActions = {
    onSelect: setSelectedId,
    onSource: setSourceView,
    onAsk,
    onPublish: async (tileId) => {
      const published = await api<TilePublication>(
        `/api/boards/${board.id}/tiles/${tileId}/publications`,
        token,
        json({ dashboard_id: dashboardId }),
      );
      sendToHost("widgets-changed", { dashboard_id: published.dashboard_id });
    },
    onMove: (tileId, position) => {
      const from = tiles.findIndex((tile) => tile.id === tileId);
      if (
        from === -1 ||
        position < 0 ||
        position >= tiles.length ||
        from === position
      )
        return;
      const moved = [...tiles];
      const [tile] = moved.splice(from, 1);
      moved.splice(position, 0, tile);
      showTiles(moved);
      void change("Moving the tile", () =>
        api(
          `/api/boards/${board.id}/tiles/${tileId}`,
          token,
          patch({ position }),
        ),
      );
    },
    onRename: (tileId, title) => {
      showTiles(
        tiles.map((tile) => (tile.id === tileId ? { ...tile, title } : tile)),
      );
      void change("Renaming the tile", () =>
        api(`/api/boards/${board.id}/tiles/${tileId}`, token, patch({ title })),
      );
    },
    onRemove: (tileId) => {
      setSelectedId(null);
      showTiles(tiles.filter((tile) => tile.id !== tileId));
      void change("Removing the tile", () =>
        api(`/api/boards/${board.id}/tiles/${tileId}`, token, {
          method: "DELETE",
        }),
      );
    },
  };

  const columns = columnsOf(tiles);
  const indexOf = new Map(tiles.map((tile, index) => [tile.id, index]));

  function renderUnits(units: Unit[]) {
    return units.map((unit, unitIndex) => {
      const isLast = unitIndex === units.length - 1;
      const cards = unit.tiles.map((tile) => {
        const index = indexOf.get(tile.id) ?? 0;
        return (
          <TileCard
            key={tile.id}
            tile={tile}
            index={index}
            count={tiles.length}
            isHero={index === 0}
            isSmall={unit.tiles.length === 2 && isSmall(tile.template)}
            isSelected={tile.id === selectedId}
            isGrowing={isLast && unit.tiles.length === 1}
            actions={actions}
          />
        );
      });
      if (unit.tiles.length === 1) return cards;
      return (
        <div key={unit.tiles[0].id} className={isLast ? "pair grow" : "pair"}>
          {cards}
        </div>
      );
    });
  }

  return (
    <>
      {actionError !== null && (
        <div className="board-note" role="alert">
          <span>{actionError}</span>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={() => setActionError(null)}
          >
            OK
          </button>
        </div>
      )}
      {loadError !== null && (
        <div className="board-note" role="alert">
          <span>
            The board could not be brought up to date. {loadError.message}
          </span>
          <button type="button" onClick={() => void load()}>
            Try again
          </button>
        </div>
      )}
      {tiles.length === 0 ? (
        <div className="state">
          <h1>{board.name} has no tiles yet</h1>
          <p>
            Ask the chat to add one, for example: “Show what I spend on
            groceries” or “When does my salary come?”
          </p>
        </div>
      ) : (
        <div className="cols" onClick={() => setSelectedId(null)}>
          <div className="stack">{renderUnits(columns.left)}</div>
          {columns.right.length > 0 ? (
            <div className="stack">{renderUnits(columns.right)}</div>
          ) : (
            <div className="stack">
              <p className="more-hint">
                This board is small on purpose: it shows only what your accounts
                say about it. Tell the chat what else belongs here.
              </p>
            </div>
          )}
        </div>
      )}
      {board.dropped.length > 0 && (
        <p className="dropped">
          {board.dropped.length === 1
            ? "1 tile could not be filled: "
            : `${board.dropped.length} tiles could not be filled: `}
          {board.dropped
            .map((dropped) => `${dropped.title} (${dropped.reason})`)
            .join("; ")}
        </p>
      )}
      <SourceDrawer view={sourceView} onClose={() => setSourceView(null)} />
    </>
  );
}
