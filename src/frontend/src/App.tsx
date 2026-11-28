import { useEffect, useRef, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "./api";
import { AlertLine, NeedsAttention } from "./alerts/NeedsAttention";
import { BoardScreen } from "./board/BoardScreen";
import { Dock } from "./board/Dock";
import { Mark, SmallIcon } from "./board/icons";
import { NewBoard } from "./board/NewBoard";
import type { Board, BoardPlan, BoardSummary, Tile } from "./board/types";
import { CategorizationView } from "./categories/CategorizationView";
import { BuildTrace } from "./chat/BuildTrace";
import { ChatPanel } from "./chat/ChatPanel";
import { DemoReset } from "./DemoReset";
import type { ConversationRef } from "./chat/types";
import { type HostContext, sendToHost, useHostContext } from "./host";
import { useDebugMode } from "./lib/debugMode";
import { useStream } from "./lib/useStream";
import { ProfilePanel } from "./profile/ProfilePanel";
import { SPLIT, Split } from "./Split";

type View = "board" | "categories";

// The chat links to the Categorization view with this hash.
const CATEGORIES_HASH = "#categories";

function viewOfHash(): View | null {
  return window.location.hash === CATEGORIES_HASH ? "categories" : null;
}

export function App() {
  const context = useHostContext();
  // Counts the demo resets: a wiped customer gets a fresh page, as on a first visit.
  const [resets, setResets] = useState(0);
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
      key={`${context.customer?.customer_id ?? "anonymous"}-${resets}`}
      context={context}
      onReset={() => setResets((count) => count + 1)}
    />
  );
}

type Loading =
  | { state: "loading" }
  | { state: "building" }
  | { state: "error"; error: RequestError }
  | { state: "ready" };

function TrustRoom({
  context,
  onReset,
}: {
  context: HostContext;
  onReset: () => void;
}) {
  const token = context.access_token;
  // The board's share of the screen, and the last split to come back to.
  const [share, setShare] = useState(SPLIT);
  const [lastSplit, setLastSplit] = useState(SPLIT);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [view, setView] = useState<View>(() => viewOfHash() ?? "board");
  // Counts the openings, so the drawer loads what the chat changed while it was closed.
  const [profileOpenings, setProfileOpenings] = useState(0);
  const isDebugMode = useDebugMode();
  // The side panel over an e-banking page is for asking; boards live on /trustroom.
  const isChatOnly =
    context.mode === "panel" && context.page.id !== "dashboard";
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
  // A board the chat just made and the customer has not opened yet.
  const [freshId, setFreshId] = useState<string | null>(null);
  const [customerSince, setCustomerSince] = useState<string | null>(null);
  const [plans, setPlans] = useState<BoardPlan[]>([]);
  // The board the chat is about, null for a chat about no board; it follows the board opened.
  const [chatBoardId, setChatBoardId] = useState<string | null>(null);
  // A chat picked from the list about another board, or about none, for the chat that opens next.
  const [picked, setPicked] = useState<ConversationRef | null>(null);
  const profileButton = useRef<HTMLButtonElement>(null);
  const drawerClose = useRef<HTMLButtonElement>(null);
  const build = useStream<BoardPlan>();
  const buildLog = useRef<HTMLDivElement>(null);

  // The trace follows the step that is running, in the column or, when narrow, in the page.
  useEffect(() => {
    buildLog.current?.lastElementChild?.scrollIntoView({ block: "end" });
  }, [build.steps]);

  useEffect(() => {
    if (isProfileOpen) drawerClose.current?.focus({ preventScroll: true });
  }, [isProfileOpen]);

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
    try {
      setPlans(await api<BoardPlan[]>("/api/board-plans", token));
    } catch {
      // Without the plans a board's chat just does not show how it was built.
    }
    return sorted;
  }

  // A customer without boards gets their first ones, built from their own data.
  async function start() {
    setLoading({ state: "loading" });
    try {
      let list = await fetchBoards();
      if (list.length === 0) {
        setLoading({ state: "building" });
        await build.start("/api/board-plans?stream=true", token, {});
        list = await fetchBoards();
      }
      setOpenId(list[0]?.id ?? null);
      setChatBoardId(list[0]?.id ?? null);
      setLoading({ state: "ready" });
      // Only now, so sorting the bookings never slows the first boards down.
      void startCategorisation();
    } catch (error) {
      setLoading({ state: "error", error: requestErrorOf(error) });
    }
  }

  // Categorises the bookings that have none yet, in the background on the server.
  async function startCategorisation() {
    try {
      await api("/api/categorisations", token, json({}));
    } catch {
      // Not urgent: the Categorization view starts it again when it opens.
    }
  }

  // A link to #categories in a chat answer opens the Categorization view, on /trustroom.
  useEffect(() => {
    function follow() {
      if (viewOfHash() === null) return;
      if (isChatOnly) sendToHost("navigate", { path: "/trustroom" });
      else setView("categories");
    }
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, [isChatOnly]);

  function showView(next: View) {
    setView(next);
    const { pathname, search } = window.location;
    window.history.replaceState(
      null,
      "",
      next === "categories" ? CATEGORIES_HASH : `${pathname}${search}`,
    );
  }

  // Once per customer; the ref keeps StrictMode's second run from building the boards twice.
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;
    void start();
  }, []);

  function changeShare(next: number) {
    setShare(next);
    if (next > 0 && next < 1) setLastSplit(next);
  }

  // The chat comes along to the board it opens, as its newest chat.
  function openBoard(boardId: string | null) {
    setPicked(null);
    setAskTile(null);
    setOpenId(boardId);
    if (boardId !== null) setChatBoardId(boardId);
    if (boardId === freshId) setFreshId(null);
    if (share === 0) setShare(lastSplit);
  }

  function openTrustRoom() {
    sendToHost("navigate", { path: "/trustroom" });
  }

  function openConversation(conversation: ConversationRef) {
    if (conversation.board_id !== null) openBoard(conversation.board_id);
    setAskTile(null);
    setChatBoardId(conversation.board_id);
    setPicked(conversation);
  }

  // A tile is asked about in its board's chat, so the chat moves there first.
  function askAbout(tile: Tile) {
    if (openId !== null && chatBoardId !== openId) {
      setPicked(null);
      setChatBoardId(openId);
    }
    setAskTile({ id: tile.id, title: tile.title });
    if (share === 1) setShare(lastSplit);
  }

  function openProfile() {
    setProfileOpenings((count) => count + 1);
    setIsProfileOpen(true);
  }

  function closeProfile() {
    setIsProfileOpen(false);
    profileButton.current?.focus();
  }

  async function handleBoardChanged(boardId?: string) {
    setRefreshKey((key) => key + 1);
    try {
      await fetchBoards();
    } catch {
      // The board itself is fetched again by its screen, which shows its own error.
    }
    // The chat stays where its answer is; the new tab gets a dot until it is opened.
    if (boardId !== undefined) setFreshId(boardId);
  }

  async function handleCreated(board: Board) {
    try {
      await fetchBoards();
    } catch {
      const summary: BoardSummary = {
        id: board.id,
        name: board.name,
        position: board.position,
        plan_id: board.plan_id,
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
    if (chatBoardId === boardId) setChatBoardId(remaining[0]?.id ?? null);
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
  const chatBoard = boards.find((board) => board.id === chatBoardId) ?? null;
  const isBoardShown = share > 0;

  const boardSide = (
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
          <NeedsAttention
            token={token}
            customerId={customer?.customer_id ?? "anonymous"}
            onOpenSettings={openProfile}
          />
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
              onAsk={askAbout}
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
            freshId={freshId}
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
      {loading.state === "ready" && (
        <button
          type="button"
          className="askfab"
          data-shown={share === 1 ? "" : undefined}
          tabIndex={share === 1 ? 0 : -1}
          onClick={() => setShare(lastSplit)}
        >
          <SmallIcon name="ask" />
          {openBoardSummary === null
            ? "Open the chat"
            : `Ask about ${openBoardSummary.name}`}
        </button>
      )}
    </section>
  );

  let chatSide = null;
  if (loading.state === "building") {
    chatSide = (
      <section
        className="tr-chat"
        data-variant="side"
        aria-label="How your first board is built"
      >
        <div className="talk-in">
          <div className="chathead">
            <b>Chat</b>
            <span>building your first board</span>
          </div>
          <div className="msgs" ref={buildLog}>
            <div className="bot">
              I am building your first board from your own accounts and
              bookings.
              {isDebugMode && " Every step shows here as it happens."}
            </div>
            {isDebugMode ? (
              <BuildTrace steps={build.steps} isLive isOpen />
            ) : (
              <span className="status" role="status">
                Building…
              </span>
            )}
          </div>
        </div>
      </section>
    );
  }
  if (loading.state === "ready") {
    chatSide = (
      <ChatPanel
        key={chatBoardId ?? "no-board"}
        variant={isBoardShown ? "side" : "page"}
        initialConversationId={
          picked?.board_id === chatBoardId ? (picked?.id ?? null) : null
        }
        boards={boards}
        board={
          chatBoard === null ? null : { id: chatBoard.id, name: chatBoard.name }
        }
        newChatBoardId={isBoardShown ? openId : null}
        plan={plans.find((plan) => plan.id === chatBoard?.plan_id) ?? null}
        tile={askTile}
        isBoardShown={isBoardShown}
        onToggleBoard={() => setShare(isBoardShown ? 0 : lastSplit)}
        onClose={() => setShare(1)}
        onClearTile={() => setAskTile(null)}
        onBoardChanged={(boardId) => void handleBoardChanged(boardId)}
        onOpenBoard={openBoard}
        onOpenConversation={openConversation}
      />
    );
  }

  if (isChatOnly) {
    chatSide = (
      <ChatPanel
        variant="page"
        initialConversationId={null}
        boards={boards}
        board={null}
        newChatBoardId={null}
        plan={null}
        tile={null}
        isBoardShown={false}
        onToggleBoard={openTrustRoom}
        onClose={() => sendToHost("close")}
        onClearTile={() => setAskTile(null)}
        onBoardChanged={(boardId) => void handleBoardChanged(boardId)}
        onOpenBoard={openTrustRoom}
        // Only a board's chat leaves the panel's chat: it opens on /trustroom.
        onOpenConversation={openTrustRoom}
      />
    );
  }

  return (
    <div
      className="app"
      data-building={loading.state === "building" ? "" : undefined}
    >
      <header className="top">
        <div className="brand">
          <Mark />
          <span>TrustRoom</span>
          <span className="private">
            <SmallIcon name="lock" size={12} />
            Stays inside the bank
          </span>
        </div>
        <div className="tail">
          <DemoReset token={token} onDone={onReset} />
          <button
            ref={profileButton}
            className="me"
            type="button"
            aria-expanded={isProfileOpen}
            aria-label={
              isProfileOpen
                ? `Close the profile of ${name}`
                : `Open the profile of ${name}`
            }
            onClick={() => (isProfileOpen ? closeProfile() : openProfile())}
          >
            <span className="avatar">{initials}</span>
            <span>
              <b>{name}</b>
              <small>Profile and documents</small>
            </span>
          </button>
        </div>
      </header>
      {isChatOnly ? (
        <div className="main chat-only">
          <AlertLine token={token} reloadKey={context.page.path} />
          {chatSide}
        </div>
      ) : view === "categories" ? (
        <div className="main">
          <CategorizationView token={token} onBack={() => showView("board")} />
        </div>
      ) : chatSide === null ? (
        <div className="main">{boardSide}</div>
      ) : (
        <Split
          share={share}
          onShare={changeShare}
          board={boardSide}
          chat={chatSide}
        />
      )}
      <div
        className="scrim"
        data-shown={isProfileOpen ? "" : undefined}
        onClick={closeProfile}
      />
      <div
        className="profile-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`Profile of ${name}`}
        data-shown={isProfileOpen ? "" : undefined}
        inert={!isProfileOpen}
        onKeyDown={(event) => event.key === "Escape" && closeProfile()}
      >
        <button
          type="button"
          ref={drawerClose}
          className="profile-close"
          aria-label="Close the profile"
          onClick={closeProfile}
        >
          <SmallIcon name="close" />
        </button>
        <ProfilePanel
          key={profileOpenings}
          name={name}
          initials={initials}
          customerSince={customerSince}
          onOpenCategorization={() => {
            closeProfile();
            // The side panel has no room for it: Categorization opens on /trustroom.
            if (isChatOnly) openTrustRoom();
            else showView("categories");
          }}
        />
      </div>
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
  const isDebugMode = useDebugMode();
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
  if (loading.state === "building") {
    return (
      <div className="state" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <h1>Building your first boards</h1>
        <p>
          From your own accounts and bookings, about what matters to you. This
          takes a moment, once.
          {isDebugMode && " The chat shows each step."}
        </p>
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
