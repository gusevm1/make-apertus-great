import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "../api";
import { useHostContext } from "../host";

// The chat announces a saved proposal with this event, so the notes reload.
const NOTES_CHANGED = "trustroom:notes-changed";

interface Note {
  id: string;
  text: string;
}

interface StoredDocument {
  id: string;
  name: string;
  kind: string | null;
  title: string | null;
}

const KIND_LABELS: Record<string, string> = {
  payslip: "Payslip",
  pension_certificate: "Pension certificate",
  insurance_policy: "Insurance policy",
  contract: "Contract",
  offer: "Offer",
  invoice: "Invoice",
  reminder: "Payment reminder",
  statement: "Statement",
  other: "Document",
};

export function ProfilePanel(props: {
  name: string;
  initials: string;
  customerSince: string | null;
}) {
  const context = useHostContext();
  const year = props.customerSince?.match(/\d{4}/)?.[0];
  return (
    <aside className="tr-profile" aria-label="Your profile">
      <div className="who">
        <span className="avatar">{props.initials}</span>
        <span>
          <b>{props.name}</b>
          {year !== undefined && <span>Customer since {year}</span>}
        </span>
      </div>
      {context === null ? (
        <p className="hint">Waiting for the e-banking…</p>
      ) : (
        <>
          <Notes token={context.access_token} />
          <Documents token={context.access_token} />
        </>
      )}
      <p className="foot">
        Only you and your TrustRoom see this. You can change or delete every
        note and every document.
      </p>
    </aside>
  );
}

function plural(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`;
}

function Notes({ token }: { token: string }) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState<RequestError | null>(null);

  async function load() {
    setError(null);
    try {
      setNotes(await api<Note[]>("/api/context-entries", token));
    } catch (failure) {
      setError(requestErrorOf(failure));
    }
  }

  useEffect(() => {
    void load();
    const reload = () => void load();
    window.addEventListener(NOTES_CHANGED, reload);
    return () => window.removeEventListener(NOTES_CHANGED, reload);
  }, []);

  return (
    <div className="sec">
      <h2>
        What I know about you
        {notes !== null && <span>{plural(notes.length, "note", "notes")}</span>}
      </h2>
      <div className="card">
        {error !== null && (
          <Failure
            message={error.message}
            detail="Your notes were not loaded."
            onRetry={() => void load()}
          />
        )}
        {error === null && notes === null && <p className="hint">Loading…</p>}
        {notes?.length === 0 && (
          <p className="hint">
            Nothing yet. When I learn something worth keeping, I ask before I
            save it.
          </p>
        )}
        {notes?.map((note) => (
          <NoteRow
            key={note.id}
            token={token}
            note={note}
            onChanged={(next) =>
              setNotes((current) =>
                (current ?? []).flatMap((other) =>
                  other.id !== note.id ? [other] : next === null ? [] : [next],
                ),
              )
            }
          />
        ))}
      </div>
    </div>
  );
}

function NoteRow({
  token,
  note,
  onChanged,
}: {
  token: string;
  note: Note;
  onChanged: (next: Note | null) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setIsSending(true);
    setFailure(null);
    try {
      await action();
    } catch (error) {
      setFailure(requestErrorOf(error).message);
    } finally {
      setIsSending(false);
    }
  }

  function save() {
    const text = draft?.trim() ?? "";
    if (text === "") return;
    if (text === note.text) return setDraft(null);
    void run(async () => {
      // A change makes a new entry; the old one is kept by the backend.
      const updated = await api<Note>(
        `/api/context-entries/${note.id}`,
        token,
        {
          ...json({ text }),
          method: "PATCH",
        },
      );
      onChanged(updated);
    });
  }

  function remove() {
    void run(async () => {
      await api<void>(`/api/context-entries/${note.id}`, token, {
        method: "DELETE",
      });
      onChanged(null);
    });
  }

  if (draft === null) {
    return (
      <div className="fact">
        <p>{note.text}</p>
        <button
          className="icon sm"
          type="button"
          aria-label="Edit this note"
          onClick={() => setDraft(note.text)}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M8.6 2.6 11.4 5.4 5 11.8H2.2V9Z" />
          </svg>
        </button>
      </div>
    );
  }
  return (
    <div className="fact editing">
      <textarea
        value={draft}
        maxLength={300}
        rows={3}
        aria-label="Note"
        onChange={(event) => setDraft(event.target.value)}
        disabled={isSending}
      />
      {failure !== null && (
        <p className="error-note" role="alert">
          {failure}
        </p>
      )}
      <div className="acts">
        <button
          className="btn go"
          type="button"
          disabled={isSending || draft.trim() === ""}
          onClick={save}
        >
          Save
        </button>
        <button
          className="btn"
          type="button"
          disabled={isSending}
          onClick={() => setDraft(null)}
        >
          Cancel
        </button>
        <button
          className="btn danger"
          type="button"
          disabled={isSending}
          onClick={remove}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function Documents({ token }: { token: string }) {
  const [documents, setDocuments] = useState<StoredDocument[] | null>(null);
  const [error, setError] = useState<RequestError | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);

  async function load() {
    setError(null);
    try {
      setDocuments(await api<StoredDocument[]>("/api/documents", token));
    } catch (failure) {
      setError(requestErrorOf(failure));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Cleared, so choosing the same file again fires the event again.
    event.target.value = "";
    if (file === undefined) return;
    setUploadError(null);
    setIsUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api("/api/documents", token, { method: "POST", body: form });
      await load();
    } catch (failure) {
      setUploadError(requestErrorOf(failure).message);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="sec">
      <h2>
        Your documents
        {documents !== null && (
          <span>{plural(documents.length, "file", "files")}</span>
        )}
      </h2>
      <div className="card">
        {error !== null && (
          <Failure
            message={error.message}
            detail="Your documents were not loaded."
            onRetry={() => void load()}
          />
        )}
        {error === null && documents === null && (
          <p className="hint">Loading…</p>
        )}
        {documents?.length === 0 && (
          <p className="hint">
            Nothing yet. Add a payslip, a contract or a reminder and I can read
            it.
          </p>
        )}
        {documents?.map((document) => (
          <DocumentRow
            key={document.id}
            token={token}
            document={document}
            onDeleted={() =>
              setDocuments((current) =>
                (current ?? []).filter((other) => other.id !== document.id),
              )
            }
          />
        ))}
      </div>
      {uploadError !== null && (
        <p className="error-note" role="alert">
          {uploadError} The document was not added.
        </p>
      )}
      <input
        ref={picker}
        type="file"
        className="visually-hidden"
        tabIndex={-1}
        accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
        onChange={(event) => void handleFile(event)}
      />
      <button
        className="drop"
        type="button"
        disabled={isUploading}
        onClick={() => picker.current?.click()}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <path d="M7 2.5v9M2.5 7h9" />
        </svg>
        {isUploading ? "Reading the document…" : "Add a document"}
      </button>
    </div>
  );
}

function DocumentRow({
  token,
  document,
  onDeleted,
}: {
  token: string;
  document: StoredDocument;
  onDeleted: () => void;
}) {
  const [isAsking, setIsAsking] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const dot = document.name.lastIndexOf(".");
  const badge =
    dot === -1 ? "FILE" : document.name.slice(dot + 1, dot + 5).toUpperCase();
  const kind =
    document.kind === null ? null : (KIND_LABELS[document.kind] ?? null);

  async function remove() {
    setIsSending(true);
    setFailure(null);
    try {
      await api<void>(`/api/documents/${document.id}`, token, {
        method: "DELETE",
      });
      onDeleted();
    } catch (error) {
      setFailure(requestErrorOf(error).message);
      setIsSending(false);
    }
  }

  return (
    <div className="doc">
      <span className="pdf">{badge}</span>
      <span className="doc-text">
        <b>{document.title ?? document.name}</b>
        {kind !== null && <span>{kind}</span>}
        {failure !== null && <span className="error-note">{failure}</span>}
      </span>
      {isAsking ? (
        <span className="acts">
          <button
            className="btn danger sm"
            type="button"
            disabled={isSending}
            onClick={() => void remove()}
          >
            Delete
          </button>
          <button
            className="btn sm"
            type="button"
            disabled={isSending}
            onClick={() => setIsAsking(false)}
          >
            Keep
          </button>
        </span>
      ) : (
        <button
          className="icon sm"
          type="button"
          aria-label={`Delete ${document.name}`}
          onClick={() => setIsAsking(true)}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M2.5 4h9M5.5 4V2.5h3V4M3.8 4l.5 7.5h5.4l.5-7.5" />
          </svg>
        </button>
      )}
    </div>
  );
}

function Failure({
  message,
  detail,
  onRetry,
}: {
  message: string;
  detail: string;
  onRetry: () => void;
}) {
  return (
    <div className="failure" role="alert">
      <p>
        <strong>{message}</strong>
        {detail}
      </p>
      <button type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
