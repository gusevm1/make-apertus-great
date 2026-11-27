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
  type ToolCall,
} from "./api";
import { type HostContext, useHostContext } from "./host";
import { Canvas, shownViewOf, type View, type Visual } from "./Canvas";
import { Confirmation } from "./Confirmation";
import { ChatList, type ChatListProps, Home } from "./Home";
import { Icon } from "./Icon";
import { canCaptureAudio } from "./lib/audioCapture";
import { Markdown } from "./lib/markdown";
import { useStream } from "./lib/useStream";
import { Trace } from "./Trace";
import { useVoiceInput } from "./useVoiceInput";

export function App() {
  const context = useHostContext();
  if (context === null) {
    return <p className="hint">Waiting for the e-banking…</p>;
  }
  // A new customer logging in gets a fresh chat, never the previous customer's state.
  return <Chat key={context.customer?.customer_id} context={context} />;
}

function Chat({ context }: { context: HostContext }) {
  const token = context.access_token;
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoadingChats, setIsLoadingChats] = useState(true);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [pendingDocuments, setPendingDocuments] = useState<DocumentRef[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isOpening, setIsOpening] = useState(false);
  const [attached, setAttached] = useState<DocumentRef[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  // Filled once widgets exist (#25); until then the canvas shows its empty state.
  const [visual] = useState<Visual | null>(null);
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
  }

  const isHome = conversationId === null && pending === null;

  // The chat follows new text until the customer scrolls up, and again once they are back down.
  // The home starts at its top.
  useEffect(() => {
    const chat = chatRef.current;
    if (chat === null) return;
    if (isHome) chat.scrollTop = 0;
    else if (isFollowing.current) chat.scrollTop = chat.scrollHeight;
  }, [isHome, messages, pending, stream.text, stream.toolCalls.length]);

  // The stored chats come back after a reload, listed on the home in the panel and the full page.
  useEffect(() => {
    let isCurrent = true;
    async function load() {
      try {
        const stored = await api<Conversation[]>("/api/conversations", token);
        if (isCurrent) setConversations(stored);
      } catch (error) {
        if (isCurrent) setLoadError(messageOf(error));
      } finally {
        if (isCurrent) setIsLoadingChats(false);
      }
    }
    void load();
    return () => {
      isCurrent = false;
    };
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
    setLoadError(null);
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
      const reply = await stream.start(`${path}/messages?stream=true`, token, {
        content,
        document_ids: documents.map((document) => document.id),
        page: pageOf(context),
      });
      if (reply === null) {
        if (createdId !== null) await discardEmptyChat(createdId);
        restoreQuestion(content, documents);
        return;
      }
      // The reply is stored. A failed reload only costs the tool lines, never a second send.
      try {
        await open(id);
      } catch (error) {
        setLoadError(messageOf(error));
      }
      stream.reset();
    } catch (error) {
      setLoadError(messageOf(error));
      if (createdId !== null) await discardEmptyChat(createdId);
      restoreQuestion(content, documents);
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

  async function handleConfirmation(toolCallId: string, isAllowed: boolean) {
    await api<void>(
      `/api/conversations/${conversationId}/tool-calls/${toolCallId}/confirmations`,
      token,
      json({ is_allowed: isAllowed }),
    );
  }

  async function handleAttach(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Cleared, so choosing the same file again fires the event again.
    event.target.value = "";
    if (file === undefined) return;
    setLoadError(null);
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
      setLoadError(messageOf(error));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleOpen(id: string) {
    setLoadError(null);
    // The chat list is disabled meanwhile, so two picks cannot finish out of order.
    setIsOpening(true);
    try {
      await open(id);
    } catch (error) {
      setLoadError(messageOf(error));
    } finally {
      setIsOpening(false);
    }
  }

  function handleNewChat() {
    setConversationId(null);
    setMessages([]);
    setToolCalls([]);
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
      ?.title ?? pending;
  const error = stream.error ?? loadError ?? voice.error;
  const errorNote = error !== null && (
    <p className="error-note" role="alert">
      {error}
    </p>
  );
  const shownView = shownViewOf({
    view,
    isWaiting: waitingCalls.length > 0,
    hasError: error !== null,
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
          <ChatList {...chats} />
        </aside>

        <div className="canvas-pane">
          <Canvas
            visual={visual}
            isBusy={isBusy}
            onAsk={(text) => void ask(text)}
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
                >
                  <Markdown text={message.content} />
                </Answer>
              ),
            )}
            {pending !== null && (
              <>
                <Question text={pending} documents={pendingDocuments} />
                <Answer steps={stream.toolCalls} provenance={null}>
                  {stream.text !== "" ? (
                    <Markdown text={stream.text} />
                  ) : (
                    waitingCalls.length === 0 && (
                      <p className="hint">Thinking…</p>
                    )
                  )}
                </Answer>
              </>
            )}
            {!isHome && errorNote}
          </section>

          {waitingCalls.map((toolCall) => (
            <Confirmation
              key={toolCall.id}
              toolCall={toolCall}
              onAnswer={(isAllowed) =>
                handleConfirmation(toolCall.id, isAllowed)
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
  children,
}: {
  steps: Parameters<typeof Trace>[0]["steps"];
  provenance: Message["provenance"];
  children: ReactNode;
}) {
  return (
    <article className="answer">
      <Trace steps={steps} />
      <div className="answer-text">{children}</div>
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

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}
