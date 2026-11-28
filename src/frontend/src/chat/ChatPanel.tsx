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
import { Markdown } from "../lib/markdown";
import { useStream } from "../lib/useStream";
import type { BoardPlan } from "../board/types";
import { useVoiceInput } from "../useVoiceInput";
import { Answer } from "./Answer";
import { BuildTrace } from "./BuildTrace";
import { Composer } from "./Composer";
import {
  type ChatMessage,
  type ContextEntry,
  type ConversationRef,
  createdBoardOf,
  ranBoardTool,
} from "./types";

export interface ChatPanelProps {
  variant: "side" | "page";
  conversationId: string | null;
  boardConversationIds: string[];
  board: { id: string; name: string } | null;
  /** How the open board was built; null for the page chat and for a board started empty. */
  plan: BoardPlan | null;
  tile: { id: string; title: string } | null;
  onClearTile: () => void;
  onBoardChanged: (boardId?: string) => void;
  onOpenBoard: (boardId: string) => void;
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
  conversationId,
  boardConversationIds,
  board,
  plan,
  tile,
  onClearTile,
  onBoardChanged,
  onOpenBoard,
}: ChatPanelProps & { context: HostContext }) {
  const token = context.access_token;
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
  const resolving = useRef<Promise<string> | null>(null);
  const loadRequest = useRef(0);
  const knownIds = useRef(boardConversationIds);
  knownIds.current = boardConversationIds;
  const scroller = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
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

  // The page chat is the customer's newest chat that belongs to no board, or a new one.
  async function resolveConversation(): Promise<string> {
    const all = await api<ConversationRef[]>("/api/conversations", token);
    const own = all
      .filter((conversation) => !knownIds.current.includes(conversation.id))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    if (own.length > 0) return own[0].id;
    const created = await api<ConversationRef>(
      "/api/conversations",
      token,
      json({ title: "Chat" }),
    );
    return created.id;
  }

  useEffect(() => {
    const request = ++loadRequest.current;
    setLoad("loading");
    setFailed(null);
    stream.reset();
    async function open() {
      try {
        if (conversationId !== null) resolving.current = null;
        else resolving.current ??= resolveConversation();
        const id = conversationId ?? (await resolving.current);
        const data = await fetchConversation(id);
        if (request !== loadRequest.current) return;
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
  }, [conversationId, reloadKey]);

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
        const asked = data.messages.findLast((message) => message.role === "user");
        const calls = data.toolCalls.filter(
          (call) => call.message_id === asked?.id,
        );
        if (ranBoardTool(calls)) onBoardChanged(createdBoardOf(calls));
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
        : variant === "page"
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
      {load === "ready" && plan !== null && plan.trace.length > 0 && (
        <BuildTrace
          steps={plan.trace}
          isLive={false}
          isOpen={loaded.messages.length === 0 && !isStreaming}
        />
      )}
      {isEmpty && (
        <p className="hint">
          Ask a question, or tell me what this board should show.
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
        <Turn text={failedQuestion.content} documents={failedQuestion.documents} />
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

  return (
    <section
      className="tr-chat"
      data-variant={variant}
      aria-label={variant === "side" ? "Chat about this board" : "Chat"}
    >
      <div className="talk-in">
        {variant === "side" && (
          <div className="chathead">
            <b>Chat</b>
            {board !== null && <span>about {board.name}</span>}
          </div>
        )}
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
            setAttached((current) => current.filter((other) => other.id !== id))
          }
          onClearTile={onClearTile}
          onVoiceStart={voice.start}
          onVoiceStop={voice.stop}
        />
      </div>
    </section>
  );
}

/** The customer's message, with the documents sent along as file cards. */
function Turn({
  text,
  documents,
}: {
  text: string;
  documents: DocumentRef[];
}) {
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

