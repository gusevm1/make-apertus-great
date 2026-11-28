import { useEffect, useRef, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "./api";
import { BoardScreen } from "./board/BoardScreen";
import { Dock } from "./board/Dock";
import { Mark, SmallIcon } from "./board/icons";
import { NewBoard } from "./board/NewBoard";
import type { Board, BoardSummary, Tile } from "./board/types";
import { ChatPanel } from "./chat/ChatPanel";
import { type HostContext, useHostContext } from "./host";
import { ProfilePanel } from "./profile/ProfilePanel";

type Mode = "board" | "chat";

export function App() {
  const context = useHostContext();
  if (context === null) {
    return (
      <div className="app">
        <div className="state" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <p>Waiting for the e-banking…</p>
        </div>
      </div>
    );
  }
  // A new customer logging in gets a fresh page, never the previous customer's state.
  return (
    <TrustRoom
      key={context.customer?.customer_id ?? "anonymous"}
      context={context}
    />
  );
}

type Loading =
  | { state: "loading" }
  | { state: "building" }
  | { state: "error"; error: RequestError }
  | { state: "ready" };

// What the page says while the first boards are built, one line every few seconds.
const BUILDING_LINES = [
  "Reading your accounts",
  "Looking at the last months",
  "Choosing what matters",
  "Drawing your first board",
];
const BUILDING_LINE_MS = 4_000;

function TrustRoom({ context }: { context: HostContext }) {
  const token = context.access_token;
  const [mode, setMode] = useState<Mode>("board");
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [loading, setLoading] = useState<Loading>({ state: "loading" });
  // The open board, or null for the new-board screen.
  const [openId, setOpenId] = useState<string | null>(null);
  const [askTile, setAskTile] = useState<{ id: string; title: string } | null>(
    null,
  );
  const [refreshKey, setRefreshKey] = useState(0);
  const [dockError, setDockError] = useState<string | null>(null);
  const hasStarted = useRef(false);
  const [customerSince, setCustomerSince] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    async function load() {
      try {
        const data = await api<{ customer_since: string | null }>(
          "/api/customer",
          token,
        );
        if (isCurrent) setCustomerSince(data.customer_since);
      } catch {
        // The profile shows no year then; nothing else depends on it.
      }
    }
    void load();
    return () => {
      isCurrent = false;
    };
  }, [token]);

  const customer = context.customer;
  const name =
    customer === null
      ? "Your profile"
      : `${customer.first_name} ${customer.last_name}`;
  const initials =
    customer === null
      ? ""
      : `${customer.first_name.charAt(0)}${customer.last_name.charAt(0)}`;

  async function fetchBoards(): Promise<BoardSummary[]> {
    const list = await api<BoardSummary[]>("/api/boards", token);
    const sorted = [...list].sort(
      (first, second) => first.position - second.position,
    );
    setBoards(sorted);
    return sorted;
  }

  // A customer without boards gets their first ones, built from their own data.
  async function start() {
    setLoading({ state: "loading" });
    try {
      let list = await fetchBoards();
      if (list.length === 0) {
        setLoading({ state: "building" });
        await api("/api/board-plans", token, json({}));
        list = await fetchBoards();
      }
      setOpenId(list[0]?.id ?? null);
      setLoading({ state: "ready" });
    } catch (error) {
      setLoading({ state: "error", error: requestErrorOf(error) });
    }
  }

  // Once per customer; the ref keeps StrictMode's second run from building the boards twice.
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;
    void start();
  }, []);

  function openBoard(boardId: string | null) {
    setAskTile(null);
    setOpenId(boardId);
  }

  async function handleBoardChanged(boardId?: string) {
    setRefreshKey((key) => key + 1);
    try {
      await fetchBoards();
    } catch {
      // The board itself is fetched again by its screen, which shows its own error.
    }
    if (boardId !== undefined) {
      setMode("board");
      openBoard(boardId);
    }
  }

  async function handleCreated(board: Board) {
    try {
      await fetchBoards();
    } catch {
      const summary: BoardSummary = {
        id: board.id,
        name: board.name,
        position: board.position,
        conversation_id: board.conversation_id,
        tile_count: board.tiles.length,
      };
      setBoards((current) => [...current, summary]);
    }
    openBoard(board.id);
  }

  async function handleRenameBoard(boardId: string, boardName: string) {
    setDockError(null);
    setBoards((current) =>
      current.map((board) =>
        board.id === boardId ? { ...board, name: boardName } : board,
      ),
    );
    try {
      await api(`/api/boards/${boardId}`, token, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: boardName }),
      });
    } catch (error) {
      setDockError(
        `The board was not renamed. ${requestErrorOf(error).message}`,
      );
    }
    await fetchBoards().catch(() => undefined);
  }

  async function handleDeleteBoard(boardId: string) {
    setDockError(null);
    const remaining = boards.filter((board) => board.id !== boardId);
    setBoards(remaining);
    if (openId === boardId) openBoard(remaining[0]?.id ?? null);
    try {
      await api(`/api/boards/${boardId}`, token, { method: "DELETE" });
    } catch (error) {
      setDockError(
        `The board was not deleted. ${requestErrorOf(error).message}`,
      );
    }
    await fetchBoards().catch(() => undefined);
  }

  // The chip above the chat input follows the tile: renamed with it, gone with it.
  function handleTilesChanged(tiles: Tile[]) {
    setAskTile((current) => {
      if (current === null) return null;
      const tile = tiles.find((other) => other.id === current.id);
      return tile === undefined ? null : { id: tile.id, title: tile.title };
    });
  }

  const openBoardSummary = boards.find((board) => board.id === openId) ?? null;
  const boardConversationIds = boards
    .map((board) => board.conversation_id)
    .filter((id) => id !== null);

  return (
    <div className="app" data-mode={mode}>
      <header className="top">
        <div className="brand">
          <Mark />
          <span>TrustRoom</span>
          <span className="private">
            <SmallIcon name="lock" size={12} />
            Stays inside the bank
          </span>
        </div>
        <nav className="mode" aria-label="What to show">
          <button
            type="button"
            aria-pressed={mode === "board"}
            onClick={() => setMode("board")}
          >
            <SmallIcon name="board" />
            Board and chat
          </button>
          <button
            type="button"
            aria-pressed={mode === "chat"}
            onClick={() => setMode("chat")}
          >
            <SmallIcon name="ask" />
            Chat
          </button>
        </nav>
        <button
          className="me"
          type="button"
          aria-expanded={mode === "chat"}
          aria-label={
            mode === "chat"
              ? `Close the profile of ${name}`
              : `Open the profile of ${name}`
          }
          onClick={() => setMode(mode === "chat" ? "board" : "chat")}
        >
          <span className="avatar">{initials}</span>
          <span>
            <b>{name}</b>
            <small>Profile and documents</small>
          </span>
        </button>
      </header>

      {mode === "chat" ? (
        <div className="main">
          <ChatPanel
            variant="page"
            conversationId={null}
            boardConversationIds={boardConversationIds}
            board={null}
            tile={null}
            onClearTile={() => setAskTile(null)}
            onBoardChanged={(boardId) => void handleBoardChanged(boardId)}
            onOpenBoard={(boardId) => {
              setMode("board");
              openBoard(boardId);
            }}
          />
          <ProfilePanel name={name} initials={initials} customerSince={customerSince} />
        </div>
      ) : (
        <div className="main">
          <section
            className="boardcol"
            aria-label={
              openBoardSummary === null
                ? "New board"
                : `Board ${openBoardSummary.name}`
            }
          >
            {loading.state === "ready" ? (
              <>
                {openBoardSummary === null ? (
                  <NewBoard
                    token={token}
                    onCreated={(board) => void handleCreated(board)}
                  />
                ) : (
                  <BoardScreen
                    key={openBoardSummary.id}
                    token={token}
                    boardId={openBoardSummary.id}
                    boardName={openBoardSummary.name}
                    refreshKey={refreshKey}
                    onAsk={(tile) =>
                      setAskTile({ id: tile.id, title: tile.title })
                    }
                    onTilesChanged={handleTilesChanged}
                  />
                )}
                {dockError !== null && (
                  <p className="dropped" role="alert">
                    {dockError}
                  </p>
                )}
                <Dock
                  boards={boards}
                  openId={openId}
                  isNewOpen={openBoardSummary === null}
                  onOpen={openBoard}
                  onNew={() => openBoard(null)}
                  onRename={(boardId, boardName) =>
                    void handleRenameBoard(boardId, boardName)
                  }
                  onDelete={(boardId) => void handleDeleteBoard(boardId)}
                />
              </>
            ) : (
              <FirstBoards loading={loading} onRetry={() => void start()} />
            )}
          </section>
          {loading.state === "ready" && openBoardSummary !== null && (
            <ChatPanel
              key={openBoardSummary.id}
              variant="side"
              conversationId={openBoardSummary.conversation_id}
              boardConversationIds={boardConversationIds}
              board={{ id: openBoardSummary.id, name: openBoardSummary.name }}
              tile={askTile}
              onClearTile={() => setAskTile(null)}
              onBoardChanged={(boardId) => void handleBoardChanged(boardId)}
              onOpenBoard={openBoard}
            />
          )}
        </div>
      )}
    </div>
  );
}

/** The page before the boards are there: loading the list, or building the first boards. */
function FirstBoards({
  loading,
  onRetry,
}: {
  loading: Loading;
  onRetry: () => void;
}) {
  const [lineIndex, setLineIndex] = useState(0);
  const isBuilding = loading.state === "building";

  useEffect(() => {
    if (!isBuilding) return;
    const timer = window.setInterval(
      () => setLineIndex((index) => (index + 1) % BUILDING_LINES.length),
      BUILDING_LINE_MS,
    );
    return () => window.clearInterval(timer);
  }, [isBuilding]);

  if (loading.state === "error") {
    return (
      <div className="state" role="alert">
        <h1>Your boards did not load</h1>
        <p>{loading.error.message}</p>
        <button type="button" className="button go" onClick={onRetry}>
          Try again
        </button>
      </div>
    );
  }
  if (isBuilding) {
    return (
      <div className="state" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <h1>Building your first boards</h1>
        <p>
          From your own accounts and bookings, about what matters to you. This
          takes up to two minutes, once.
        </p>
        <p className="line">{BUILDING_LINES[lineIndex]}…</p>
      </div>
    );
  }
  return (
    <div className="state" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>Opening your boards…</p>
    </div>
  );
}
