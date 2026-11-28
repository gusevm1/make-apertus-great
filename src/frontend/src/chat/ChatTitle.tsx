import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { SmallIcon } from "../board/icons";

export const TITLE_LENGTH = 60;
export const NEW_CHAT = "New chat";

type Rename =
  | { action: "refuse" }
  | { action: "close" }
  | { action: "save"; title: string };

/** What Enter does with the typed name: refuse a blank one, close on no change, else save. */
export function renameOf(draft: string, current: string | null): Rename {
  const title = draft.trim().slice(0, TITLE_LENGTH);
  if (title === "") return { action: "refuse" };
  if (title === current) return { action: "close" };
  return { action: "save", title };
}

/** The open chat's name in the chat bar, which turns into an input to rename the chat. */
export function ChatTitle({
  title,
  about,
  onRename,
}: {
  title: string | null;
  about: string;
  /** Null while no chat is open, so there is nothing to rename. */
  onRename: ((title: string) => Promise<void>) | null;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [isRefused, setIsRefused] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const isRefocusing = useRef(false);
  const shown = title ?? NEW_CHAT;

  useEffect(() => {
    if (draft !== null || !isRefocusing.current) return;
    isRefocusing.current = false;
    button.current?.focus();
  }, [draft]);

  function close(refocus: boolean) {
    isRefocusing.current = refocus;
    setIsRefused(false);
    setDraft(null);
  }

  async function submit(typed: string) {
    const rename = renameOf(typed, title);
    if (rename.action === "refuse") return setIsRefused(true);
    close(true);
    if (rename.action === "close" || onRename === null) return;
    try {
      await onRename(rename.title);
      setIsFailed(false);
    } catch {
      setIsFailed(true);
      setDraft(rename.title);
    }
  }

  function handleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void submit(event.currentTarget.value);
    }
    if (event.key === "Escape") {
      event.stopPropagation();
      close(true);
    }
  }

  let note = about;
  if (isRefused) note = "A chat needs a name.";
  else if (isFailed) note = "Could not rename this chat.";

  return (
    <div className="chatname">
      {onRename === null && <b>{shown}</b>}
      {onRename !== null && draft === null && (
        <button
          ref={button}
          type="button"
          title="Rename this chat"
          onClick={() => setDraft(title ?? "")}
        >
          <b>{shown}</b>
          <SmallIcon name="rename" size={12} />
        </button>
      )}
      {onRename !== null && draft !== null && (
        <input
          value={draft}
          maxLength={TITLE_LENGTH}
          aria-label="Name of this chat"
          aria-invalid={isRefused}
          placeholder={NEW_CHAT}
          autoFocus
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => {
            setIsRefused(false);
            setIsFailed(false);
            setDraft(event.target.value);
          }}
          onKeyDown={handleKey}
          onBlur={() => close(false)}
        />
      )}
      <span role={isRefused || isFailed ? "alert" : undefined}>{note}</span>
    </div>
  );
}
