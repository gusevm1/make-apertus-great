import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
  useLayoutEffect,
} from "react";
import type { DocumentRef } from "../api";
import { canCaptureAudio } from "../lib/audioCapture";
import { CloseIcon, MicIcon, PaperclipIcon, SendIcon } from "./icons";

const DOCUMENTS_PER_MESSAGE = 3;

/** The input of the chat: the tile chip, attachments, voice and send. */
export function Composer({
  inputRef,
  question,
  placeholder,
  isDisabled,
  isBusy,
  isUploading,
  attached,
  tile,
  voicePhase,
  onChange,
  onSubmit,
  onAttach,
  onDetach,
  onClearTile,
  onVoiceStart,
  onVoiceStop,
}: {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  question: string;
  placeholder: string;
  isDisabled: boolean;
  isBusy: boolean;
  isUploading: boolean;
  attached: DocumentRef[];
  tile: { id: string; title: string } | null;
  voicePhase: string;
  onChange: (text: string) => void;
  onSubmit: () => void;
  onAttach: (file: File) => void;
  onDetach: (id: string) => void;
  onClearTile: () => void;
  onVoiceStart: () => void;
  onVoiceStop: () => void;
}) {
  const canSend = !isBusy && !isDisabled && question.trim() !== "";

  // Grows with the text up to the CSS max-height, then scrolls.
  useLayoutEffect(() => {
    const input = inputRef.current;
    if (input === null) return;
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  }, [inputRef, question]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  function handleKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    )
      return;
    event.preventDefault();
    if (canSend) onSubmit();
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Cleared, so choosing the same file again fires the event again.
    event.target.value = "";
    if (file !== undefined) onAttach(file);
  }

  return (
    <form
      className="compose"
      aria-label="Ask TrustRoom"
      onSubmit={handleSubmit}
    >
      {tile !== null && (
        <span className="about">
          {tile.title}
          <button
            type="button"
            aria-label="Stop talking about this tile"
            onClick={onClearTile}
          >
            <CloseIcon />
          </button>
        </span>
      )}
      {(attached.length > 0 || isUploading) && (
        <ul className="attached">
          {attached.map((document) => (
            <li key={document.id}>
              <span>{document.name}</span>
              <button
                type="button"
                aria-label={`Remove ${document.name}`}
                onClick={() => onDetach(document.id)}
              >
                <CloseIcon />
              </button>
            </li>
          ))}
          {isUploading && <li className="reading">Reading the document…</li>}
        </ul>
      )}
      <div className="inputrow">
        <textarea
          ref={inputRef}
          rows={1}
          value={question}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          aria-label="Message"
          autoComplete="off"
          disabled={isDisabled}
        />
        <label className="icon" aria-label="Attach a document">
          <PaperclipIcon />
          <input
            type="file"
            className="visually-hidden"
            accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx"
            disabled={isBusy || attached.length >= DOCUMENTS_PER_MESSAGE}
            onChange={handleFile}
          />
        </label>
        {canCaptureAudio() &&
          (voicePhase === "recording" ? (
            <button
              type="button"
              className="recording"
              aria-pressed="true"
              onClick={onVoiceStop}
            >
              <span className="recording-dot" /> Stop
            </button>
          ) : (
            <button
              type="button"
              className="icon"
              aria-label="Speak"
              disabled={voicePhase !== "idle"}
              onClick={onVoiceStart}
            >
              <MicIcon />
            </button>
          ))}
        <button
          type="submit"
          className="icon send"
          aria-label="Send"
          disabled={!canSend}
        >
          <SendIcon />
        </button>
      </div>
    </form>
  );
}
