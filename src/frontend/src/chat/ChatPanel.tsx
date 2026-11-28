import { useEffect, useRef, useState } from "react";
import {
  api,
  type DocumentRef,
  json,
  type RequestError,
  requestErrorOf,
  type ToolCall,
} from "../api";
import { Confirmation } from "../Confirmation";
import { type HostContext, useHostContext } from "../host";
import { useDebugMode } from "../lib/debugMode";
import { Markdown } from "../lib/markdown";
import { useStream } from "../lib/useStream";
import { SmallIcon } from "../board/icons";
import type { BoardPlan } from "../board/types";
import { useVoiceInput } from "../useVoiceInput";
import { Answer } from "./Answer";
import { AnswerTrace } from "./AnswerTrace";
import { BuildTrace } from "./BuildTrace";
import { ChatHistory } from "./ChatHistory";
import { ChatTitle, TITLE_LENGTH } from "./ChatTitle";
import { Composer } from "./Composer";
import {
  type ChatMessage,
  type ContextEntry,
  type ConversationRef,
  createdBoardOf,
  ranBoardTool,
} from "./types";

export interface ChatPanelProps {
  /** Beside the board, or wide while the board is hidden. */
  variant: "side" | "page";
  /** A chat picked from another board's panel, opened first; null opens the newest one. */
  initialConversationId: string | null;
  /** Every board, to say in the list of chats which board a chat is about. */
  boards: { id: string; name: string }[];
  board: { id: string; name: string } | null;
  /** Where a new chat goes: the board on screen, or null for no board. */
  newChatBoardId: string | null;
  /** How the open board was built; null for the page chat and for a board started empty. */
  plan: BoardPlan | null;
  tile: { id: string; title: string } | null;
  isBoardShown: boolean;
  onToggleBoard: () => void;
  onClose: () => void;
  onClearTile: () => void;
  onBoardChanged: (boardId?: string) => void;
  onOpenBoard: (boardId: string) => void;
  /** A chat about another board, or about none, was picked from the list. */
  onOpenConversation: (conversation: ConversationRef) => void;
}

export function ChatPanel(props: ChatPanelProps) {
  const context = useHostContext();
  if (context === null) {
    return (
      <section className="tr-chat" data-variant={props.variant}>
        <p className="hint pad">Waiting for the e-banking…</p>
      </section>
    );
  }
  // A new customer gets a fresh chat, never the previous customer's state.
  return (
    <ChatInner
      key={context.customer?.customer_id}
      context={context}
      {...props}
    />
  );
}

interface Loaded {
  messages: ChatMessage[];
  toolCalls: ToolCall[];
  proposals: ContextEntry[];
}

type Failed =
  | { name: "ask"; content: string; documents: DocumentRef[] }
  | { name: "upload"; file: File };

// Within this many pixels of the end, the chat counts as scrolled to the end.
const FOLLOW_DISTANCE = 40;
const PAGE_TEXT_LENGTH = 200;

function ChatInner({
  context,
  variant,
  initialConversationId,
  boards,
  board,
  newChatBoardId,
  plan,
  tile,
  isBoardShown,
  onToggleBoard,
  onClose,
  onClearTile,
  onBoardChanged,
  onOpenBoard,
  onOpenConversation,
}: ChatPanelProps & { context: HostContext }) {
  const token = context.access_token;
  const boardId = board?.id ?? null;
  const [chosenId, setChosenId] = useState(initialConversationId);
  const [conversations, setConversations] = useState<ConversationRef[]>([]);
  // The list as it is now, for a naming that runs after a streamed answer.
  const latestConversations = useRef(conversations);
  latestConversations.current = conversations;
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<Loaded>({
    messages: [],
    toolCalls: [],
    proposals: [],
  });
  const [load, setLoad] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<RequestError | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [pendingDocuments, setPendingDocuments] = useState<DocumentRef[]>([]);
  const [attached, setAttached] = useState<DocumentRef[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [failed, setFailed] = useState<{
    error: RequestError;
    action: Failed;
  } | null>(null);
  const resolving = useRef<{
    chosenId: string | null;
    result: Promise<{ id: string; all: ConversationRef[] }>;
  } | null>(null);
  const loadRequest = useRef(0);
  const scroller = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isFollowing = useRef(true);
  const lastScrollTop = useRef(0);
  const stream = useStream<ChatMessage>();
  const voice = useVoiceInput({
    token,
    onTranscript: (text) =>
      setQuestion((current) => (current === "" ? text : `${current} ${text}`)),
  });

  async function fetchConversation(id: string): Promise<Loaded> {
    const path = `/api/conversations/${id}`;
    const [messages, toolCalls, proposals] = await Promise.all([
      api<ChatMessage[]>(`${path}/messages`, token),
      api<ToolCall[]>(`${path}/tool-calls`, token),
      // Without the list a proposal just shows no card.
      api<ContextEntry[]>("/api/context-entries?status=proposed", token).catch(
        () => [],
      ),
    ]);
    return { messages, toolCalls, proposals };
  }

  /** A new chat about a board, or about none. */
  async function createConversation(
    aboutId: string | null,
  ): Promise<ConversationRef> {
    return aboutId === null
      ? api<ConversationRef>("/api/conversations", token, json({}))
      : api<ConversationRef>(`/api/boards/${aboutId}/conversations`, token, {
          method: "POST",
        });
  }

  // The chat to open: the chosen one, else the newest about this board, else a new one.
  async function resolveConversation() {
    const all = await api<ConversationRef[]>("/api/conversations", token);
    const own = all.filter((conversation) => conversation.board_id === boardId);
    const chosen = own.find((conversation) => conversation.id === chosenId);
    const existing = chosen ?? own[0];
    if (existing !== undefined) return { id: existing.id, all };
    const created = await createConversation(boardId);
    return { id: created.id, all: [created, ...all] };
  }

  useEffect(() => {
    const request = ++loadRequest.current;
    setLoad("loading");
    setFailed(null);
    stream.reset();
    async function open() {
      try {
        // StrictMode's second run shares the first one's request, so no chat is made twice.
        if (resolving.current?.chosenId !== chosenId)
          resolving.current = { chosenId, result: resolveConversation() };
        const { id, all } = await resolving.current.result;
        const data = await fetchConversation(id);
        if (request !== loadRequest.current) return;
        setConversations(all);
        setActiveId(id);
        setLoaded(data);
        setLoad("ready");
      } catch (error) {
        if (request !== loadRequest.current) return;
        resolving.current = null;
        setLoadError(requestErrorOf(error));
        setLoad("error");
      }
    }
    void open();
  }, [chosenId, reloadKey]);

  // The chat follows new text until the customer scrolls up, and again once they are back down.
  useEffect(() => {
    const element = scroller.current;
    // An empty chat opens on the top of the build trace, not on its end.
    if (loaded.messages.length === 0 && pending === null) return;
    if (element !== null && isFollowing.current)
      element.scrollTop = element.scrollHeight;
  }, [loaded, pending, stream.text, stream.toolCalls.length, load]);

  function handleScroll() {
    const element = scroller.current;
    if (element === null) return;
    const distance =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    if (element.scrollTop < lastScrollTop.current) isFollowing.current = false;
    if (distance < FOLLOW_DISTANCE) isFollowing.current = true;
    lastScrollTop.current = element.scrollTop;
  }

  async function ask(content: string) {
    if (content === "" || activeId === null || stream.status === "streaming")
      return;
    const documents = attached;
    isFollowing.current = true;
    setQuestion("");
    setAttached([]);
    setPending(content);
    setPendingDocuments(documents);
    setFailed(null);
    try {
      const path = `/api/conversations/${activeId}`;
      await stream.start(`${path}/messages?stream=true`, token, {
        content,
        document_ids: documents.map((document) => document.id),
        page: pageOf(context),
        ...(board !== null ? { board_id: board.id } : {}),
        ...(tile !== null ? { tile_id: tile.id } : {}),
      });
      // The reply is stored. A failed reload only costs the extras, never a second send.
      try {
        const data = await fetchConversation(activeId);
        setLoaded(data);
        const asked = data.messages.findLast(
          (message) => message.role === "user",
        );
        const calls = data.toolCalls.filter(
          (call) => call.message_id === asked?.id,
        );
        if (ranBoardTool(calls)) onBoardChanged(createdBoardOf(calls));
        void nameAfter(activeId, content);
      } catch (error) {
        setLoadError(requestErrorOf(error));
        setLoad("error");
      }
      stream.reset();
      voice.clear();
    } catch (error) {
      setQuestion((current) => (current === "" ? content : current));
      setAttached((current) => (current.length === 0 ? documents : current));
      setFailed({
        error: requestErrorOf(error),
        action: { name: "ask", content, documents },
      });
    } finally {
      setPending(null);
    }
  }

  // A chat without a title is named after its first question.
  async function nameAfter(id: string, content: string) {
    const current = latestConversations.current.find(
      (other) => other.id === id,
    );
    if (current?.title !== null) return;
    try {
      await rename({ id, title: content.slice(0, TITLE_LENGTH) });
    } catch {
      // The chat keeps its place in the list without a name.
    }
  }

  async function rename({ id, title }: { id: string; title: string }) {
    await api<ConversationRef>(`/api/conversations/${id}`, token, {
      ...json({ title }),
      method: "PATCH",
    });
    setConversations((current) =>
      current.map((other) => (other.id === id ? { ...other, title } : other)),
    );
  }

  // Deleting the open chat opens the newest one left about this board, or a new one.
  async function remove({ id }: { id: string }) {
    await api<void>(`/api/conversations/${id}`, token, { method: "DELETE" });
    setConversations((current) => current.filter((other) => other.id !== id));
    if (id !== activeId) return;
    resolving.current = null;
    setChosenId(null);
    setReloadKey((current) => current + 1);
  }

  async function startChat() {
    setFailed(null);
    setIsHistoryOpen(false);
    try {
      const created = await createConversation(newChatBoardId);
      // A chat about another board, or about none, opens where that chat lives.
      if (newChatBoardId !== boardId) return onOpenConversation(created);
      resolving.current = {
        chosenId: created.id,
        result: Promise.resolve({
          id: created.id,
          all: [created, ...conversations],
        }),
      };
      setChosenId(created.id);
    } catch (error) {
      setLoadError(requestErrorOf(error));
      setLoad("error");
    }
  }

  function pick(conversation: ConversationRef) {
    setIsHistoryOpen(false);
    if (conversation.board_id === boardId) setChosenId(conversation.id);
    else onOpenConversation(conversation);
  }

  async function upload(file: File) {
    setFailed(null);
    setIsUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const document = await api<DocumentRef>("/api/documents", token, {
        method: "POST",
        body: form,
      });
      setAttached((current) => [...current, document]);
    } catch (error) {
      setFailed({
        error: requestErrorOf(error),
        action: { name: "upload", file },
      });
    } finally {
      setIsUploading(false);
    }
  }

  async function handleConfirmation(
    toolCallId: string,
    isAllowed: boolean,
    edited: Record<string, unknown> | null,
  ) {
    await api<void>(
      `/api/conversations/${activeId}/tool-calls/${toolCallId}/confirmations`,
      token,
      json({ is_allowed: isAllowed, arguments: edited }),
    );
  }

  function retry() {
    if (failed === null) return voice.retry();
    if (failed.action.name === "ask") void ask(failed.action.content);
    else void upload(failed.action.file);
  }

  const isStreaming = pending !== null;
  const active = conversations.find((other) => other.id === activeId);
  const isDebugMode = useDebugMode();
  const isBusy = isStreaming || isUploading || stream.status === "streaming";
  const waitingCalls = stream.toolCalls.filter(
    (call) => call.confirmation !== null && call.isRunning,
  );
  const failedQuestion = failed?.action.name === "ask" ? failed.action : null;
  const failure =
    failed === null
      ? voice.failure
      : { title: failed.error.message, detail: detailOf(failed) };
  const isEmpty =
    load === "ready" &&
    loaded.messages.length === 0 &&
    !isStreaming &&
    failedQuestion === null;
  const runningCall = stream.toolCalls.findLast((call) => call.isRunning);
  let status = "Thinking…";
  if (stream.isChecking) status = "Checking the figures…";
  else if (runningCall !== undefined) status = `${runningCall.title}…`;
  else if (stream.round !== null) status = "Planning…";

  const placeholder =
    waitingCalls.length > 0
      ? "Answer the question above first"
      : voice.phase === "transcribing"
        ? "Transcribing…"
        : board === null
          ? "Ask anything about your money"
          : "Ask, or change the board";

  const thread = (
    <>
      {load === "loading" && <p className="hint">Loading the chat…</p>}
      {load === "error" && (
        <div className="failure" role="alert">
          <p>
            <strong>{loadError?.message ?? "Something went wrong."}</strong>
            The chat was not loaded.
          </p>
          <button type="button" onClick={() => setReloadKey((key) => key + 1)}>
            Try again
          </button>
        </div>
      )}
      {isEmpty && (
        <p className="ai-notice">
          You are talking to an AI. It works with your own data only and gives
          no investment advice.
        </p>
      )}
      {isDebugMode &&
        load === "ready" &&
        plan !== null &&
        plan.trace.length > 0 && (
          <BuildTrace
            steps={plan.trace}
            isLive={false}
            isOpen={loaded.messages.length === 0 && !isStreaming}
          />
        )}
      {isEmpty && (
        <p className="hint">
          {board === null
            ? "Ask anything about your money."
            : "Ask a question, or tell me what this board should show."}
        </p>
      )}
      {load !== "error" &&
        loaded.messages.map((message, index) =>
          message.role === "user" ? (
            <Turn
              key={message.id}
              text={message.content}
              documents={message.documents}
            />
          ) : (
            <Answer
              key={message.id}
              token={token}
              text={message.content}
              // Tool calls are stored on the question they answer.
              calls={loaded.toolCalls.filter(
                (call) => call.message_id === loaded.messages[index - 1]?.id,
              )}
              provenance={message.provenance}
              proposals={loaded.proposals}
              onOpenBoard={onOpenBoard}
            />
          ),
        )}
      {isStreaming && (
        <>
          <Turn text={pending} documents={pendingDocuments} />
          <div className="bot">
            {isDebugMode && stream.toolCalls.length > 0 && (
              <AnswerTrace calls={stream.toolCalls} provenance={null} isLive />
            )}
            {stream.text !== "" && <Markdown text={stream.text} />}
            {waitingCalls.length === 0 && (
              <span className="status" role="status">
                {status}
              </span>
            )}
          </div>
        </>
      )}
      {failedQuestion !== null && (
        <Turn
          text={failedQuestion.content}
          documents={failedQuestion.documents}
        />
      )}
      {failure !== null && (
        <div className="failure" role="alert">
          <p>
            <strong>{failure.title}</strong>
            {failure.detail}
          </p>
          <button
            type="button"
            onClick={retry}
            disabled={isBusy || voice.phase !== "idle"}
          >
            Try again
          </button>
        </div>
      )}
    </>
  );

  // An empty chat is the new chat already, unless a new one goes elsewhere.
  const isNewChatDisabled =
    isBusy ||
    load !== "ready" ||
    (newChatBoardId === boardId && loaded.messages.length === 0);

  return (
    <section
      className="tr-chat"
      data-variant={variant}
      aria-label={board === null ? "Chat" : `Chat about ${board.name}`}
    >
      <div className="chatbar">
        <button
          type="button"
          className="tool"
          aria-pressed={isBoardShown}
          aria-label={isBoardShown ? "Hide the board" : "Show the board"}
          title={isBoardShown ? "Hide the board" : "Show the board"}
          onClick={onToggleBoard}
        >
          <SmallIcon name="board" />
        </button>
        <ChatTitle
          key={activeId}
          title={active?.title ?? null}
          about={board === null ? "about no board" : `about ${board.name}`}
          onRename={
            active === undefined
              ? null
              : (title) => rename({ id: active.id, title })
          }
        />
        <button
          type="button"
          className="tool"
          aria-expanded={isHistoryOpen}
          aria-label="Your chats"
          title="Your chats"
          onClick={() => setIsHistoryOpen(!isHistoryOpen)}
        >
          <SmallIcon name="history" />
        </button>
        <button
          type="button"
          className="tool"
          aria-label="New chat"
          title="New chat"
          onClick={() => void startChat()}
          disabled={isNewChatDisabled}
        >
          <SmallIcon name="rename" />
        </button>
        <button
          type="button"
          className="tool"
          aria-label="Close the chat"
          title="Close the chat"
          onClick={onClose}
        >
          <SmallIcon name="close" />
        </button>
      </div>
      <div className="chatbody">
        <ChatHistory
          isOpen={isHistoryOpen}
          conversations={conversations}
          isLoading={load === "loading"}
          activeId={activeId}
          boardId={boardId}
          boards={boards}
          onPick={pick}
          onRename={(id, title) => rename({ id, title })}
          onDelete={(id) => remove({ id })}
          onClose={() => setIsHistoryOpen(false)}
        />
        <div className="talk-in">
          <div
            className="msgs"
            ref={scroller}
            onScroll={handleScroll}
            aria-live="polite"
          >
            {thread}
          </div>
          {waitingCalls.map((call) => (
            <Confirmation
              key={call.id}
              toolCall={call}
              onAnswer={(isAllowed, edited) =>
                handleConfirmation(call.id, isAllowed, edited)
              }
            />
          ))}
          <Composer
            inputRef={inputRef}
            question={question}
            placeholder={placeholder}
            isDisabled={waitingCalls.length > 0 || load !== "ready"}
            isBusy={isBusy}
            isUploading={isUploading}
            attached={attached}
            tile={tile}
            voicePhase={voice.phase}
            onChange={setQuestion}
            onSubmit={() => void ask(question.trim())}
            onAttach={(file) => void upload(file)}
            onDetach={(id) =>
              setAttached((current) =>
                current.filter((other) => other.id !== id),
              )
            }
            onClearTile={onClearTile}
            onVoiceStart={voice.start}
            onVoiceStop={voice.stop}
          />
        </div>
      </div>
    </section>
  );
}

/** The customer's message, with the documents sent along as file cards. */
function Turn({ text, documents }: { text: string; documents: DocumentRef[] }) {
  return (
    <div className="turn">
      {documents.map((document) => (
        <div key={document.id} className="file">
          <span className="pdf">{extensionOf(document.name)}</span>
          <b>{document.name}</b>
        </div>
      ))}
      <div className="you">{text}</div>
    </div>
  );
}

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "FILE" : name.slice(dot + 1, dot + 5).toUpperCase();
}

/** The page for the prompt; the e-banking has pages without a title. */
function pageOf(context: HostContext) {
  const title = context.page.title.trim().slice(0, PAGE_TEXT_LENGTH);
  if (title === "") return null;
  const account = context.account?.name.trim().slice(0, PAGE_TEXT_LENGTH);
  return { title, account_name: account === "" ? null : (account ?? null) };
}

function detailOf({
  error,
  action,
}: {
  error: RequestError;
  action: Failed;
}): string {
  if (action.name === "upload") return "The document was not attached.";
  // The backend stores nothing from a turn it ends with an error.
  return error.kind === "connection"
    ? "Your question is back in the input."
    : "Nothing was saved. Your question is back in the input.";
}
