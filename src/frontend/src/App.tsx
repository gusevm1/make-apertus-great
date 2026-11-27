import {
  type ChangeEvent,
  type FormEvent,
  Fragment,
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
import { Confirmation } from "./Confirmation";
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
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isOpening, setIsOpening] = useState(false);
  const [attached, setAttached] = useState<DocumentRef[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const chatRef = useRef<HTMLElement>(null);
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

  // The chat follows new text until the customer scrolls up, and again once they are back down.
  useEffect(() => {
    const chat = chatRef.current;
    if (chat !== null && isFollowing.current)
      chat.scrollTop = chat.scrollHeight;
  }, [messages, pending, stream.text, stream.toolCalls.length]);

  // The stored chats come back after a reload, and are the same in the panel and the full page.
  useEffect(() => {
    let isCurrent = true;
    async function load() {
      try {
        const stored = await api<Conversation[]>("/api/conversations", token);
        if (!isCurrent) return;
        setConversations(stored);
        if (stored[0] !== undefined) await open(stored[0].id);
      } catch (error) {
        if (isCurrent) setLoadError(messageOf(error));
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

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const content = question.trim();
    if (content === "" || stream.status === "streaming") return;
    const documents = attached;
    isFollowing.current = true;
    setQuestion("");
    setAttached([]);
    setPending(content);
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
    // The select is disabled meanwhile, so two picks cannot finish out of order.
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
  const account = context.account ? `, account ${context.account.name}` : "";
  const waitingCalls = stream.toolCalls.filter(
    (toolCall) => toolCall.confirmation !== null && toolCall.isRunning,
  );

  return (
    <main>
      <header>
        <p className="hint">
          You are on “{context.page.title}”{account}.
        </p>
      </header>
      <nav>
        <select
          value={conversationId ?? ""}
          onChange={(event) => void handleOpen(event.target.value)}
          disabled={isBusy || conversations.length === 0}
          aria-label="Past chats"
        >
          {conversationId === null && <option value="">New chat</option>}
          {conversations.map((conversation) => (
            <option key={conversation.id} value={conversation.id}>
              {conversation.title ?? "Untitled chat"}
            </option>
          ))}
        </select>
        <button type="button" onClick={handleNewChat} disabled={isBusy}>
          New chat
        </button>
      </nav>

      <section
        ref={chatRef}
        className="chat"
        aria-live="polite"
        onScroll={handleChatScroll}
      >
        {messages.length === 0 && pending === null && (
          <>
            <p className="ai-notice">
              You are talking to an AI. It works with your own data only and
              gives no investment advice.
            </p>
            <p className="hint">
              Ask about your finances, e.g. “How much money do I have?”
            </p>
          </>
        )}
        {messages.map((message) => (
          <Fragment key={message.id}>
            <article className={`msg ${message.role}`}>
              {message.documents.map((document) => (
                <span key={document.id} className="document">
                  {document.name}
                </span>
              ))}
              {message.role === "assistant" ? (
                <Markdown text={message.content} />
              ) : (
                message.content
              )}
              {message.provenance !== null && (
                <footer>
                  {message.provenance.model},{" "}
                  {(message.provenance.latency_ms / 1000).toFixed(1)} s
                  {message.provenance.sources.map(
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
            <Trace
              steps={toolCalls.filter((call) => call.message_id === message.id)}
            />
          </Fragment>
        ))}
        {pending !== null && (
          <>
            <article className="msg user">{pending}</article>
            <Trace steps={stream.toolCalls} />
            {waitingCalls.map((toolCall) => (
              <Confirmation
                key={toolCall.id}
                toolCall={toolCall}
                onAnswer={(isAllowed) =>
                  handleConfirmation(toolCall.id, isAllowed)
                }
              />
            ))}
            {waitingCalls.length === 0 && (
              <article className="msg assistant">
                {stream.text === "" ? (
                  "Thinking…"
                ) : (
                  <Markdown text={stream.text} />
                )}
              </article>
            )}
          </>
        )}
        {(stream.error ?? loadError ?? voice.error) !== null && (
          <p className="msg error" role="alert">
            {stream.error ?? loadError ?? voice.error}
          </p>
        )}
      </section>

      {(attached.length > 0 || isUploading) && (
        <ul className="attached">
          {attached.map((document) => (
            <li key={document.id}>
              {document.name}
              <button
                type="button"
                aria-label={`Remove ${document.name}`}
                onClick={() =>
                  setAttached((current) =>
                    current.filter((other) => other.id !== document.id),
                  )
                }
              >
                ×
              </button>
            </li>
          ))}
          {isUploading && <li>Reading the document…</li>}
        </ul>
      )}

      <form onSubmit={handleSubmit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={
            voice.phase === "transcribing" ? "Transcribing…" : "Ask something"
          }
          aria-label="Your question"
          autoComplete="off"
        />
        <label className="button">
          Attach
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
            onChange={(event) => void handleAttach(event)}
            disabled={isBusy || attached.length >= DOCUMENTS_PER_MESSAGE}
            className="visually-hidden"
          />
        </label>
        {canCaptureAudio() && (
          <button
            type="button"
            onClick={voice.phase === "recording" ? voice.stop : voice.start}
            disabled={
              voice.phase === "transcribing" || voice.phase === "starting"
            }
            aria-pressed={voice.phase === "recording"}
          >
            {voice.phase === "recording" ? "Stop" : "Speak"}
          </button>
        )}
        <button type="submit" className="primary" disabled={isBusy}>
          Send
        </button>
      </form>
    </main>
  );
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
