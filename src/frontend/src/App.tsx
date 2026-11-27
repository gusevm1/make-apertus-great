import {
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  api,
  type Conversation,
  type DocumentRef,
  json,
  type Message,
  type RequestError,
  requestErrorOf,
  type ToolCall,
  type WidgetPublication,
  type WidgetVersion,
} from "./api";
import { type HostContext, sendToHost, useHostContext } from "./host";
import {
  builtWidgetOf,
  Canvas,
  captionOf,
  shownViewOf,
  type View,
  type Visual,
} from "./Canvas";
import { CategoryCenter } from "./CategoryCenter";
import { Confirmation } from "./Confirmation";
import { ChatList, type ChatListProps, Home } from "./Home";
import { Icon } from "./Icon";
import { canCaptureAudio } from "./lib/audioCapture";
import { Markdown } from "./lib/markdown";
import { useStream } from "./lib/useStream";
import { Trace } from "./Trace";
import { useVoiceInput } from "./useVoiceInput";

const CATEGORIES_HASH = "#categories";

export function App() {
  const context = useHostContext();
  const [isCenter, setIsCenter] = useState(location.hash === CATEGORIES_HASH);

  // A chat answer links to the category center with #categories.
  useEffect(() => {
    function handleHashChange() {
      setIsCenter(location.hash === CATEGORIES_HASH);
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  // Opened by our own button, Back goes back in history, so no duplicate entry is left behind.
  const isOpenedHere = useRef(false);

  function openCenter() {
    isOpenedHere.current = true;
    location.hash = CATEGORIES_HASH;
  }

  function closeCenter() {
    if (isOpenedHere.current) {
      isOpenedHere.current = false;
      history.back();
      return;
    }
    history.replaceState(null, "", location.pathname + location.search);
    setIsCenter(false);
  }

  if (context === null) {
    return <p className="hint">Waiting for the e-banking…</p>;
  }
  // A new customer logging in gets a fresh chat, never the previous customer's state.
  // The chat stays mounted behind the center, so the back button returns to the same chat.
  return (
    <>
      <div hidden={isCenter}>
        <Chat
          key={context.customer?.customer_id}
          context={context}
          onOpenCategories={openCenter}
        />
      </div>
      {isCenter && (
        <CategoryCenter
          key={context.customer?.customer_id}
          token={context.access_token}
          today={context.today}
          onBack={closeCenter}
        />
      )}
    </>
  );
}

function Chat({
  context,
  onOpenCategories,
}: {
  context: HostContext;
  onOpenCategories: () => void;
}) {
  const token = context.access_token;
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [pendingDocuments, setPendingDocuments] = useState<DocumentRef[]>([]);
  const [failed, setFailed] = useState<{
    error: RequestError;
    action: FailedAction;
  } | null>(null);
  const [isOpening, setIsOpening] = useState(false);
  const [attached, setAttached] = useState<DocumentRef[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [visual, setVisual] = useState<Visual | null>(null);
  const [isLoadingVisual, setIsLoadingVisual] = useState(false);
  // Bumped by every widget fetch and chat switch, so a late fetch never draws on another chat.
  const visualRequest = useRef(0);
  // In a narrow frame one view at a time; wider, the CSS shows both and ignores this.
  const [view, setView] = useState<View>("chat");
  const chatRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const isFollowing = useRef(true);
  const lastScrollTop = useRef(0);
  const stream = useStream<Message>();
  const voice = useVoiceInput({
    token,
    onTranscript: (text) =>
      setQuestion((current) => (current === "" ? text : `${current} ${text}`)),
  });

  async function open(id: string) {
    const path = `/api/conversations/${id}`;
    const [storedMessages, storedCalls] = await Promise.all([
      api<Message[]>(`${path}/messages`, token),
      api<ToolCall[]>(`${path}/tool-calls`, token),
    ]);
    setConversationId(id);
    setMessages(storedMessages);
    setToolCalls(storedCalls);
    return { storedMessages, storedCalls };
  }

  // Draws a widget on the canvas; a narrow frame switches to it.
  async function showWidget(widget: { widgetId: string; version: number }) {
    const request = ++visualRequest.current;
    setIsLoadingVisual(true);
    try {
      const version = await api<WidgetVersion>(
        `/api/widgets/${widget.widgetId}/versions/${widget.version}?form=live`,
        token,
      );
      if (request !== visualRequest.current) return;
      setVisual({
        widgetId: widget.widgetId,
        version: version.number,
        publishedVersion: version.published_version,
        title: version.title,
        html: version.html,
        caption: captionOf(version),
      });
      setView("visual");
    } finally {
      if (request === visualRequest.current) setIsLoadingVisual(false);
    }
  }

  // The customer's click on "Put on dashboard"; the e-banking reloads an open dashboard.
  async function publishVisual() {
    if (visual === null) return;
    const publication = await api<WidgetPublication>(
      `/api/widgets/${visual.widgetId}/publications`,
      token,
      json({ dashboard_id: context.dashboard_id }),
    );
    sendToHost("widgets-changed", { dashboard_id: publication.dashboard_id });
    setVisual((current) =>
      current !== null && current.widgetId === publication.widget_id
        ? { ...current, publishedVersion: publication.version_number }
        : current,
    );
  }

  function clearVisual() {
    visualRequest.current += 1;
    setIsLoadingVisual(false);
    setVisual(null);
  }

  async function handleOpenVisual(widget: {
    widgetId: string;
    version: number;
  }) {
    setFailed(null);
    try {
      await showWidget(widget);
    } catch (error) {
      fail(error, { name: "visual", widget });
    }
  }

  function fail(error: unknown, action: FailedAction) {
    setFailed({ error: requestErrorOf(error), action });
  }

  // A failed question stays in the thread above its note, also when its new chat was dropped.
  const failedQuestion = failed?.action.name === "ask" ? failed.action : null;
  const isHome =
    conversationId === null && pending === null && failedQuestion === null;

  // The chat follows new text until the customer scrolls up, and again once they are back down.
  // The home starts at its top.
  useEffect(() => {
    const chat = chatRef.current;
    if (chat === null) return;
    if (isHome) chat.scrollTop = 0;
    else if (isFollowing.current) chat.scrollTop = chat.scrollHeight;
  }, [isHome, messages, pending, stream.text, stream.toolCalls.length]);

  // The stored chats come back after a reload, listed on the home in the panel and the full page.
  async function loadChats() {
    setFailed(null);
    setIsLoadingChats(true);
    try {
      setConversations(await api<Conversation[]>("/api/conversations", token));
    } catch (error) {
      fail(error, { name: "load" });
    } finally {
      setIsLoadingChats(false);
    }
  }

  // Runs once per customer: Chat is keyed by the customer, and the token only changes with them.
  useEffect(() => {
    void loadChats();
  }, []);

  // Tags the customer's bookings in the background; nothing waits for it and nothing shows it.
  useEffect(() => {
    async function startCategorisation() {
      try {
        await api("/api/categorisations", token, { method: "POST" });
      } catch {
        // A failed start is retried at the next open.
      }
    }
    void startCategorisation();
    // Runs once per customer: Chat is keyed by the customer, and the token only changes with them.
  }, []);

  function handleChatScroll() {
    const chat = chatRef.current;
    if (chat === null) return;
    const distance = chat.scrollHeight - chat.scrollTop - chat.clientHeight;
    // Only the customer moves the chat up. New text that arrives before this event must not
    // count as scrolling away, or a tall chunk would stop the following for good.
    if (chat.scrollTop < lastScrollTop.current) isFollowing.current = false;
    if (distance < FOLLOW_DISTANCE) isFollowing.current = true;
    lastScrollTop.current = chat.scrollTop;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question.trim());
  }

  async function ask(content: string) {
    if (content === "" || stream.status === "streaming") return;
    // The answer streams into the chat, so a narrow frame shows the chat.
    setView("chat");
    inputRef.current?.focus();
    const documents = attached;
    isFollowing.current = true;
    // A suggestion from the home leaves a typed draft in the input.
    setQuestion((current) => (current.trim() === content ? "" : current));
    setAttached([]);
    setPending(content);
    setPendingDocuments(documents);
    setFailed(null);
    let createdId: string | null = null;
    try {
      let id = conversationId;
      if (id === null) {
        // ponytail: the first question is the title; a model-written title is a later card
        const title = content.slice(0, TITLE_LENGTH);
        const created = await api<Conversation>(
          "/api/conversations",
          token,
          json({ title }),
        );
        setConversations((current) => [created, ...current]);
        id = created.id;
        createdId = id;
        setConversationId(id);
      }
      const path = `/api/conversations/${id}`;
      await stream.start(`${path}/messages?stream=true`, token, {
        content,
        document_ids: documents.map((document) => document.id),
        page: pageOf(context),
      });
      // The reply is stored. A failed reload only costs the tool lines, never a second send.
      try {
        const { storedMessages, storedCalls } = await open(id);
        // Tool calls are stored on the question they answer, the last question of the chat.
        const asked = storedMessages.findLast(
          (message) => message.role === "user",
        );
        const built = storedCalls
          .filter((call) => call.message_id === asked?.id)
          .map(builtWidgetOf)
          .findLast((widget) => widget !== null);
        if (built !== undefined && built !== null) await showWidget(built);
      } catch (error) {
        fail(error, { name: "open", id });
      }
      stream.reset();
      voice.clear();
    } catch (error) {
      if (createdId !== null) await discardEmptyChat(createdId);
      restoreQuestion(content, documents);
      fail(error, { name: "ask", content, documents });
    } finally {
      setPending(null);
    }
  }

  // Drops a chat a failed first question left empty; a reply stored before the drop keeps it.
  async function discardEmptyChat(id: string) {
    const path = `/api/conversations/${id}`;
    try {
      const stored = await api<Message[]>(`${path}/messages`, token);
      if (stored.length > 0) return;
      await api(path, token, { method: "DELETE" });
    } catch {
      return;
    }
    setConversations((current) => current.filter((other) => other.id !== id));
    setConversationId((current) => (current === id ? null : current));
  }

  // Puts a failed question back, unless the customer has typed or dictated a new one meanwhile.
  function restoreQuestion(content: string, documents: DocumentRef[]) {
    setQuestion((current) => (current === "" ? content : current));
    setAttached((current) => (current.length === 0 ? documents : current));
  }

  async function handleConfirmation(
    toolCallId: string,
    isAllowed: boolean,
    edited: Record<string, unknown> | null,
  ) {
    await api<void>(
      `/api/conversations/${conversationId}/tool-calls/${toolCallId}/confirmations`,
      token,
      json({ is_allowed: isAllowed, arguments: edited }),
    );
  }

  async function handleAttach(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Cleared, so choosing the same file again fires the event again.
    event.target.value = "";
    if (file === undefined) return;
    await upload(file);
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
      fail(error, { name: "upload", file });
    } finally {
      setIsUploading(false);
    }
  }

  async function handleOpen(id: string) {
    setFailed(null);
    // The chat list is disabled meanwhile, so two picks cannot finish out of order.
    setIsOpening(true);
    try {
      await open(id);
      clearVisual();
    } catch (error) {
      fail(error, { name: "open", id });
    } finally {
      setIsOpening(false);
    }
  }

  // Try again repeats the failed action with what the page holds now.
  function retry() {
    if (failed === null) return voice.retry();
    const { action } = failed;
    if (action.name === "ask") void ask(action.content);
    else if (action.name === "load") void loadChats();
    else if (action.name === "open") void handleOpen(action.id);
    else if (action.name === "upload") void upload(action.file);
    else void handleOpenVisual(action.widget);
  }

  function handleNewChat() {
    setFailed(null);
    setConversationId(null);
    setMessages([]);
    setToolCalls([]);
    clearVisual();
    stream.reset();
  }

  const isBusy =
    stream.status === "streaming" ||
    pending !== null ||
    isOpening ||
    isUploading;
  const waitingCalls = stream.toolCalls.filter(
    (toolCall) => toolCall.confirmation !== null && toolCall.isRunning,
  );
  const title =
    conversations.find((conversation) => conversation.id === conversationId)
      ?.title ??
    pending ??
    failedQuestion?.content;
  const failure =
    failed === null
      ? voice.failure
      : { title: failed.error.message, detail: detailOf(failed) };
  const errorNote = failure !== null && (
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
  );
  const shownView = shownViewOf({
    view,
    isWaiting: waitingCalls.length > 0,
    hasError: failure !== null,
  });
  const isChatForced = shownView !== view;
  useEffect(() => {
    if (isChatForced) inputRef.current?.focus();
  }, [isChatForced]);
  const chats: ChatListProps = {
    conversations,
    currentId: conversationId,
    isLoading: isLoadingChats,
    isBusy,
    onOpen: (id) => void handleOpen(id),
  };

  return (
    <div className="trustroom">
      <div
        className="layout"
        data-view={shownView}
        data-has-visual={visual !== null}
      >
        <div className="switch" role="group" aria-label="Show">
          <button
            type="button"
            aria-pressed={shownView === "chat"}
            onClick={() => setView("chat")}
          >
            Chat
          </button>
          <button
            type="button"
            aria-pressed={shownView === "visual"}
            onClick={() => setView("visual")}
          >
            Visual
          </button>
        </div>

        <aside className="sidebar">
          <button type="button" onClick={handleNewChat} disabled={isBusy}>
            <Icon name="plus" size={16} /> New chat
          </button>
          <button type="button" onClick={onOpenCategories}>
            Categories
          </button>
          <ChatList {...chats} />
        </aside>

        <div className="canvas-pane">
          <Canvas
            visual={visual}
            isLoading={isLoadingVisual}
            isBusy={isBusy}
            onAsk={(text) => void ask(text)}
            onPublish={publishVisual}
          />
        </div>

        <main>
          {!isHome && (
            <header className="thread-bar">
              <button
                type="button"
                className="icon back"
                onClick={handleNewChat}
                disabled={isBusy}
                aria-label="All chats"
              >
                <Icon name="chevronLeft" />
              </button>
              <h1>{title ?? "Untitled chat"}</h1>
            </header>
          )}

          <section
            ref={chatRef}
            className="chat"
            aria-live="polite"
            onScroll={handleChatScroll}
          >
            {/* On the home the error goes first, where the customer still looks. */}
            {isHome && errorNote}
            {isHome && (
              <Home
                context={context}
                chats={chats}
                isBusy={isBusy}
                onAsk={(text) => void ask(text)}
                onOpenCategories={onOpenCategories}
              />
            )}
            {messages.map((message, index) =>
              message.role === "user" ? (
                <Question
                  key={message.id}
                  text={message.content}
                  documents={message.documents}
                />
              ) : (
                <Answer
                  key={message.id}
                  // Tool calls are stored on the question they answer.
                  steps={toolCalls.filter(
                    (call) => call.message_id === messages[index - 1]?.id,
                  )}
                  provenance={message.provenance}
                  onOpenVisual={(widget) => void handleOpenVisual(widget)}
                >
                  <Markdown text={message.content} />
                </Answer>
              ),
            )}
            {pending !== null && (
              <>
                <Question text={pending} documents={pendingDocuments} />
                <Answer
                  steps={stream.toolCalls}
                  provenance={null}
                  onOpenVisual={(widget) => void handleOpenVisual(widget)}
                >
                  {stream.text !== "" ? (
                    <Markdown text={stream.text} />
                  ) : (
                    waitingCalls.length === 0 && (
                      <p className="hint">
                        {stream.isChecking
                          ? "Checking the figures…"
                          : "Thinking…"}
                      </p>
                    )
                  )}
                </Answer>
              </>
            )}
            {failedQuestion !== null && (
              <Question
                text={failedQuestion.content}
                documents={failedQuestion.documents}
              />
            )}
            {!isHome && errorNote}
          </section>

          {waitingCalls.map((toolCall) => (
            <Confirmation
              key={toolCall.id}
              toolCall={toolCall}
              onAnswer={(isAllowed, edited) =>
                handleConfirmation(toolCall.id, isAllowed, edited)
              }
            />
          ))}
        </main>

        {/* Outside main, so the input stays at the bottom when the visual takes a narrow frame. */}
        <form
          className="composer"
          aria-label="Ask TrustRoom"
          onSubmit={handleSubmit}
        >
          {(attached.length > 0 || isUploading) && (
            <ul className="attached">
              {attached.map((document) => (
                <li key={document.id}>
                  <Icon name="file" size={14} />
                  <span>{document.name}</span>
                  <button
                    type="button"
                    className="icon"
                    aria-label={`Remove ${document.name}`}
                    onClick={() =>
                      setAttached((current) =>
                        current.filter((other) => other.id !== document.id),
                      )
                    }
                  >
                    <Icon name="close" size={12} />
                  </button>
                </li>
              ))}
              {isUploading && (
                <li className="reading">Reading the document…</li>
              )}
            </ul>
          )}
          <div className="input-row">
            <label className="icon">
              <Icon name="paperclip" />
              <input
                type="file"
                aria-label="Attach a document"
                accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
                onChange={(event) => void handleAttach(event)}
                disabled={isBusy || attached.length >= DOCUMENTS_PER_MESSAGE}
                className="visually-hidden"
              />
            </label>
            <input
              ref={inputRef}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={placeholderOf(voice.phase, waitingCalls.length > 0)}
              aria-label="Your question"
              autoComplete="off"
              disabled={waitingCalls.length > 0}
            />
            {canCaptureAudio() &&
              (voice.phase === "recording" ? (
                <button
                  type="button"
                  className="recording"
                  onClick={voice.stop}
                  aria-pressed="true"
                >
                  <span className="recording-dot" /> Stop
                </button>
              ) : (
                <button
                  type="button"
                  className="icon"
                  onClick={voice.start}
                  disabled={voice.phase !== "idle"}
                  aria-label="Speak"
                >
                  <Icon name="mic" />
                </button>
              ))}
            <button
              type="submit"
              className="send"
              disabled={isBusy || question.trim() === ""}
              aria-label="Send"
            >
              <Icon name="send" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/** The customer's question, with the documents sent along. */
function Question({
  text,
  documents,
}: {
  text: string;
  documents: DocumentRef[];
}) {
  return (
    <article className="question">
      <p>{text}</p>
      {documents.map((document) => (
        <span key={document.id} className="document">
          <Icon name="file" size={16} />
          <span>{document.name}</span>
        </span>
      ))}
    </article>
  );
}

/** One answer: how it came about, the text, and which model wrote it from which sources. */
function Answer({
  steps,
  provenance,
  onOpenVisual,
  children,
}: {
  steps: Parameters<typeof Trace>[0]["steps"];
  provenance: Message["provenance"];
  onOpenVisual: (widget: { widgetId: string; version: number }) => void;
  children: ReactNode;
}) {
  const widgets = steps.map(builtWidgetOf).filter((widget) => widget !== null);
  return (
    <article className="answer">
      <Trace steps={steps} />
      <div className="answer-text">{children}</div>
      {widgets.map((widget) => (
        <button
          key={`${widget.widgetId}-${widget.version}`}
          type="button"
          className="visual-ready"
          onClick={() => onOpenVisual(widget)}
        >
          <Icon name="chart" size={16} />
          <span>
            <strong>Visual ready</strong> {widget.title}
          </span>
          <Icon name="chevronRight" size={16} />
        </button>
      ))}
      {provenance !== null && (
        <footer>
          <span>
            {provenance.model} · {(provenance.latency_ms / 1000).toFixed(1)} s
          </span>
          {provenance.sources.map(
            (source) =>
              // Only web addresses become links; the list comes from a search result.
              source.url?.startsWith("http") === true && (
                <a
                  key={source.id}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {source.title}
                </a>
              ),
          )}
        </footer>
      )}
    </article>
  );
}

function placeholderOf(phase: string, isWaiting: boolean): string {
  if (isWaiting) return "Answer the question above first";
  if (phase === "transcribing") return "Transcribing…";
  return "Ask about your accounts";
}

const TITLE_LENGTH = 60;
// Within this many pixels of the end, the chat counts as scrolled to the end.
const FOLLOW_DISTANCE = 40;
// The backend takes at most three documents per message.
const DOCUMENTS_PER_MESSAGE = 3;
// The backend takes a page title of 1 to 200 characters.
const PAGE_TEXT_LENGTH = 200;

/** The page for the prompt; the e-banking has pages without a title, such as its not-found page. */
function pageOf(context: HostContext) {
  const title = context.page.title.trim().slice(0, PAGE_TEXT_LENGTH);
  if (title === "") return null;
  const account = context.account?.name.trim().slice(0, PAGE_TEXT_LENGTH);
  return { title, account_name: account === "" ? null : (account ?? null) };
}

type FailedAction =
  | { name: "ask"; content: string; documents: DocumentRef[] }
  | { name: "load" }
  | { name: "open"; id: string }
  | { name: "upload"; file: File }
  | { name: "visual"; widget: { widgetId: string; version: number } };

/** The note's second line: what became of what the customer sent. */
function detailOf({
  error,
  action,
}: {
  error: RequestError;
  action: FailedAction;
}): string {
  if (action.name === "ask") {
    // The backend stores nothing from a turn it ends with an error.
    return error.kind === "connection"
      ? "Your question is back in the input."
      : "Nothing was saved. Your question is back in the input.";
  }
  if (action.name === "load") return "Your chats were not loaded.";
  if (action.name === "open") return "The chat was not loaded.";
  if (action.name === "upload") return "The document was not attached.";
  return "The visual was not opened.";
}
