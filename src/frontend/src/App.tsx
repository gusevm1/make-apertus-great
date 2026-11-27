import { type FormEvent, Fragment, useEffect, useState } from "react";
import {
  api,
  type Conversation,
  json,
  type Message,
  type ToolCall,
} from "./api";
import { type HostContext, useHostContext } from "./host";
import { canCaptureAudio } from "./lib/audioCapture";
import { useStream } from "./lib/useStream";
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

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const content = question.trim();
    if (content === "" || stream.status === "streaming") return;
    setQuestion("");
    setPending(content);
    setLoadError(null);
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
        setConversationId(id);
      }
      const path = `/api/conversations/${id}`;
      const reply = await stream.start(`${path}/messages?stream=true`, token, {
        content,
        page: pageOf(context),
      });
      if (reply === null) {
        restoreQuestion(content);
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
      restoreQuestion(content);
    } finally {
      setPending(null);
    }
  }

  // Puts a failed question back, unless the customer has typed or dictated a new one meanwhile.
  function restoreQuestion(content: string) {
    setQuestion((current) => (current === "" ? content : current));
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

  const isBusy = stream.status === "streaming" || pending !== null || isOpening;
  const account = context.account ? `, account ${context.account.name}` : "";

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

      <section className="chat" aria-live="polite">
        {messages.length === 0 && pending === null && (
          <p className="hint">
            Ask about your finances, e.g. “How much money do I have?”
          </p>
        )}
        {messages.map((message) => (
          <Fragment key={message.id}>
            <article className={`msg ${message.role}`}>
              {message.content}
              {message.provenance !== null && (
                <footer>
                  {message.provenance.model},{" "}
                  {(message.provenance.latency_ms / 1000).toFixed(1)} s
                </footer>
              )}
            </article>
            {toolCalls
              .filter((call) => call.message_id === message.id)
              .map((call) => (
                <ToolLine key={call.id} title={call.title} error={call.error} />
              ))}
          </Fragment>
        ))}
        {pending !== null && (
          <>
            <article className="msg user">{pending}</article>
            {stream.toolCalls.map((call) => (
              <ToolLine
                key={call.id}
                title={call.isRunning ? `${call.title}…` : call.title}
                error={call.error}
              />
            ))}
            <article className="msg assistant">
              {stream.text === "" ? "Thinking…" : stream.text}
            </article>
          </>
        )}
        {(stream.error ?? loadError ?? voice.error) !== null && (
          <p className="msg error" role="alert">
            {stream.error ?? loadError ?? voice.error}
          </p>
        )}
      </section>

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
// The backend takes a page title of 1 to 200 characters.
const PAGE_TEXT_LENGTH = 200;

/** The page for the prompt; the e-banking has pages without a title, such as its not-found page. */
function pageOf(context: HostContext) {
  const title = context.page.title.trim().slice(0, PAGE_TEXT_LENGTH);
  if (title === "") return null;
  const account = context.account?.name.trim().slice(0, PAGE_TEXT_LENGTH);
  return { title, account_name: account === "" ? null : (account ?? null) };
}

function ToolLine({ title, error }: { title: string; error: string | null }) {
  return (
    <span className="tool">
      {title}
      {error !== null && " (failed)"}
    </span>
  );
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}
