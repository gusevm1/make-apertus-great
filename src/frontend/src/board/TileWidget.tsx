import { useEffect, useState } from "react";
import { api, type RequestError, requestErrorOf } from "../api";
import { sendToHost, useHostContext } from "../host";
import { isSmall } from "./layout";
import { TileCard } from "./TileCard";
import type { Source, Tile } from "./types";

// Where the e-banking lists what a tile's figures come from.
const SOURCE_PATHS: Record<Source["kind"], string> = {
  bookings: "/movements",
  payments: "/payments",
  accounts: "/accounts",
  positions: "/portfolio",
  loans: "/loans",
  documents: "/trustroom",
};

/** One tile of a board, alone in its frame on the e-banking dashboard, with today's figures. */
export function TileWidget({
  boardId,
  tileId,
}: {
  boardId: string;
  tileId: string;
}) {
  const token = useHostContext()?.access_token ?? null;
  const [tile, setTile] = useState<Tile | null>(null);
  const [error, setError] = useState<RequestError | null>(null);
  const [isSelected, setIsSelected] = useState(false);
  const path = `/api/boards/${boardId}/tiles/${tileId}`;

  async function load() {
    if (token === null) return;
    setError(null);
    try {
      setTile(await api<Tile>(path, token));
    } catch (failure) {
      setError(requestErrorOf(failure));
    }
  }

  useEffect(() => {
    void load();
  }, [token]);

  // A click anywhere else on the dashboard leaves the frame, and with it the toolbar.
  useEffect(() => {
    const deselect = () => setIsSelected(false);
    window.addEventListener("blur", deselect);
    return () => window.removeEventListener("blur", deselect);
  }, []);

  if (error?.status === 404) {
    return (
      <div className="state" role="status">
        <p>This tile was removed from your board.</p>
      </div>
    );
  }
  if (error !== null) {
    return (
      <div className="state" role="alert">
        <p>{error.message}</p>
        <button type="button" className="button go" onClick={() => void load()}>
          Try again
        </button>
      </div>
    );
  }
  if (tile === null || token === null) {
    return (
      <div className="state" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
      </div>
    );
  }

  return (
    <TileCard
      tile={tile}
      index={0}
      count={1}
      isHero={tile.position === 0}
      isSmall={tile.position !== 0 && isSmall(tile.template)}
      isSelected={isSelected}
      isGrowing={false}
      actions={{
        onSelect: (selectedId) => setIsSelected(selectedId !== null),
        onRename: (_, title) => {
          setTile({ ...tile, title });
          void api<Tile>(path, token, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
          }).catch((failure: unknown) => setError(requestErrorOf(failure)));
        },
        onSource: (view) => {
          const ids = view.rows
            .map((row) => row.id)
            .filter((id) => id.startsWith("BK-"));
          const query =
            view.kind === "bookings" && ids.length > 0
              ? `?ids=${ids.join(",")}`
              : "";
          sendToHost("navigate", {
            path: `${SOURCE_PATHS[view.kind]}${query}`,
          });
        },
      }}
    />
  );
}
