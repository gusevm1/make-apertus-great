import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { NEW_CHAT, renameOf, TITLE_LENGTH } from "./ChatTitle";
import type { ConversationRef } from "./types";

type Step = "menu" | "rename" | "delete";

/** Every chat, this board's first, sliding in over the thread with a search. */
export function ChatHistory({
  isOpen,
  conversations,
  isLoading,
  activeId,
  boardId,
  boards,
  onPick,
  onRename,
  onDelete,
  onClose,
}: {
  isOpen: boolean;
  conversations: ConversationRef[];
  isLoading: boolean;
  activeId: string | null;
  boardId: string | null;
  boards: { id: string; name: string }[];
  onPick: (conversation: ConversationRef) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<{ id: string; step: Step } | null>(null);
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) search.current?.focus({ preventScroll: true });
    else setOpen(null);
  }, [isOpen]);

  const words = query.trim().toLowerCase();
  const matches = conversations.filter((conversation) =>
    (conversation.title ?? NEW_CHAT).toLowerCase().includes(words),
  );
  const order = [
    ...boards.filter((board) => board.id === boardId),
    ...boards.filter((board) => board.id !== boardId),
  ];
  const groups = [
    ...order.map((board) => ({
      label: `About ${board.name}`,
      items: matches.filter(
        (conversation) => conversation.board_id === board.id,
      ),
    })),
    {
      label: "About no board",
      items: matches.filter((conversation) => conversation.board_id === null),
    },
  ].filter((group) => group.items.length > 0);

  function close(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") onClose();
  }

  async function remove(id: string) {
    await onDelete(id);
    setOpen(null);
    search.current?.focus({ preventScroll: true });
  }

  return (
    <>
      <div
        className="histback"
        data-shown={isOpen ? "" : undefined}
        onClick={onClose}
      />
      <nav
        className="histpanel"
        aria-label="Your chats"
        data-shown={isOpen ? "" : undefined}
        inert={!isOpen}
        onKeyDown={close}
      >
        <input
          ref={search}
          type="search"
          value={query}
          placeholder="Search your chats"
          aria-label="Search your chats"
          onChange={(event) => setQuery(event.target.value)}
        />
        {groups.map((group) => (
          <section key={group.label}>
            <h3>{group.label}</h3>
            {group.items.map((conversation) => (
              <HistoryRow
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === activeId}
                step={open?.id === conversation.id ? open.step : null}
                onStep={(step) =>
                  setOpen(step === null ? null : { id: conversation.id, step })
                }
                onPick={() => onPick(conversation)}
                onRename={(title) => onRename(conversation.id, title)}
                onDelete={() => remove(conversation.id)}
              />
            ))}
          </section>
        ))}
        {groups.length === 0 && (
          <p className="hint">
            {isLoading
              ? "Loading your chats…"
              : conversations.length === 0
                ? "No chats yet."
                : "No chat has these words in its name."}
          </p>
        )}
      </nav>
    </>
  );
}

/** One chat in the list, with ⋯ for renaming it in place and deleting it after a question. */
export function HistoryRow({
  conversation,
  isActive,
  step,
  onStep,
  onPick,
  onRename,
  onDelete,
}: {
  conversation: ConversationRef;
  isActive: boolean;
  step: Step | null;
  onStep: (step: Step | null) => void;
  onPick: () => void;
  onRename: (title: string) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(conversation.title ?? "");
  const [note, setNote] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const more = useRef<HTMLButtonElement>(null);
  const isRefocusing = useRef(false);
  const shown = conversation.title ?? NEW_CHAT;

  useEffect(() => {
    if (step !== null || !isRefocusing.current) return;
    isRefocusing.current = false;
    more.current?.focus();
  }, [step]);

  function go(next: Step | null) {
    setNote(null);
    if (next === "rename") setDraft(conversation.title ?? "");
    isRefocusing.current = next === null;
    onStep(next);
  }

  // Esc leaves the step, not the whole list.
  function cancel(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    go(null);
  }

  async function save() {
    const rename = renameOf(draft, conversation.title);
    if (rename.action === "refuse") return setNote("A chat needs a name.");
    if (rename.action === "close") return go(null);
    try {
      await onRename(rename.title);
      go(null);
    } catch {
      setNote("Could not rename this chat.");
    }
  }

  async function confirmDelete() {
    setIsBusy(true);
    try {
      await onDelete();
    } catch {
      setNote("Could not delete this chat.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="histrow" data-step={step ?? undefined}>
      <div className="histline">
        {step === "rename" ? (
          <input
            value={draft}
            maxLength={TITLE_LENGTH}
            aria-label={`New name for ${shown}`}
            aria-invalid={note !== null}
            placeholder={NEW_CHAT}
            autoFocus
            onFocus={(event) => event.currentTarget.select()}
            onChange={(event) => {
              setNote(null);
              setDraft(event.target.value);
            }}
            onKeyDown={(event) => {
              cancel(event);
              if (event.key !== "Enter") return;
              event.preventDefault();
              void save();
            }}
          />
        ) : (
          <button
            type="button"
            className="histpick"
            aria-current={isActive}
            onClick={onPick}
          >
            <b>{shown}</b>
            <span>{startedOf(conversation)}</span>
          </button>
        )}
        <button
          ref={more}
          type="button"
          className="histmore"
          aria-label={`Rename or delete ${shown}`}
          title="Rename or delete"
          aria-expanded={step !== null}
          onClick={() => go(step === null ? "menu" : null)}
        >
          ⋯
        </button>
      </div>
      {step === "menu" && (
        <div className="histactions" onKeyDown={cancel}>
          <button type="button" autoFocus onClick={() => go("rename")}>
            Rename
          </button>
          <button type="button" onClick={() => go("delete")}>
            Delete
          </button>
        </div>
      )}
      {step === "delete" && (
        <div
          className="histactions"
          role="group"
          aria-label="Delete this chat?"
          onKeyDown={cancel}
        >
          <span>Delete this chat?</span>
          <button
            type="button"
            className="danger"
            autoFocus
            disabled={isBusy}
            onClick={() => void confirmDelete()}
          >
            Delete
          </button>
          <button type="button" onClick={() => go(null)}>
            Cancel
          </button>
        </div>
      )}
      {note !== null && (
        <p className="histnote" role="alert">
          {note}
        </p>
      )}
    </div>
  );
}

function startedOf(conversation: ConversationRef): string {
  return new Date(conversation.created_at).toLocaleString("de-CH", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
