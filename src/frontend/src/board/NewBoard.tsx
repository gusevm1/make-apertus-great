import { type FormEvent, useEffect, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "../api";
import { canCaptureAudio } from "../lib/audioCapture";
import { useVoiceInput } from "../useVoiceInput";
import { MicIcon, SendIcon, SmallIcon } from "./icons";
import type { Board, BoardPlan, Idea } from "./types";

const ABOUT_MAX_LENGTH = 500;
const IDEAS_SHOWN = 3;

type Ideas =
  { state: "loading" } | { state: "error" } | { state: "ready"; ideas: Idea[] };

/** The "+" tab: what the new board should be about, and ideas from the customer's last months. */
export function NewBoard({
  token,
  onCreated,
}: {
  token: string;
  onCreated: (board: Board) => void;
}) {
  const [about, setAbout] = useState("");
  const [isBuilding, setIsBuilding] = useState(false);
  const [failure, setFailure] = useState<RequestError | null>(null);
  const [ideas, setIdeas] = useState<Ideas>({ state: "loading" });
  const voice = useVoiceInput({
    token,
    onTranscript: (text) =>
      setAbout((current) => (current === "" ? text : `${current} ${text}`)),
  });

  // Runs once per customer: the token only changes with them.
  useEffect(() => {
    async function loadIdeas() {
      try {
        const plans = await api<BoardPlan[]>("/api/board-plans", token);
        setIdeas({
          state: "ready",
          ideas: plans[0]?.ideas.slice(0, IDEAS_SHOWN) ?? [],
        });
      } catch {
        setIdeas({ state: "error" });
      }
    }
    void loadIdeas();
  }, []);

  async function build(text: string) {
    const topic = text.trim().slice(0, ABOUT_MAX_LENGTH);
    if (topic === "" || isBuilding) return;
    setAbout(topic);
    setFailure(null);
    setIsBuilding(true);
    try {
      const board = await api<Board>(
        "/api/boards",
        token,
        json({ about: topic }),
      );
      onCreated(board);
    } catch (error) {
      setFailure(requestErrorOf(error));
      setIsBuilding(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void build(about);
  }

  if (isBuilding) {
    return (
      <div className="state" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <h1>Building your board from your accounts…</h1>
        <p>
          The model chooses what to show for “{about.trim()}”, and the TrustRoom
          fills in every figure from your bookings. This can take up to a
          minute.
        </p>
      </div>
    );
  }

  return (
    <div className="newboard">
      <div className="ask">
        <span className="tag">
          <SmallIcon name="plus" size={12} />
          New board
        </span>
        <h1>What should this board be about?</h1>
        <p>
          Say it in your own words. I build it from your accounts, your
          documents and what I know about you.
        </p>
      </div>

      <form className="topic" onSubmit={handleSubmit}>
        <label htmlFor="topic" className="visually-hidden">
          What this board is about
        </label>
        <input
          id="topic"
          type="text"
          value={about}
          maxLength={ABOUT_MAX_LENGTH}
          autoComplete="off"
          placeholder={
            voice.phase === "transcribing"
              ? "Transcribing…"
              : "For example: what does my child cost me every month?"
          }
          onChange={(event) => setAbout(event.target.value)}
        />
        <div className="tools">
          <span className="hint">
            You can change everything on it afterwards.
          </span>
          {canCaptureAudio() &&
            (voice.phase === "recording" ? (
              <button
                type="button"
                className="round recording"
                onClick={() => void voice.stop()}
              >
                <span className="dot" aria-hidden="true" />
                Stop
              </button>
            ) : (
              <button
                type="button"
                className="round"
                aria-label="Speak"
                disabled={voice.phase !== "idle"}
                onClick={() => void voice.start()}
              >
                <MicIcon />
              </button>
            ))}
          <button
            type="submit"
            className="round send"
            aria-label="Build the board"
            disabled={about.trim() === ""}
          >
            <SendIcon />
          </button>
        </div>
      </form>

      {failure !== null && (
        <p className="error-note" role="alert">
          The board was not built. {failure.message} Your words are still in the
          field.
        </p>
      )}
      {voice.failure !== null && (
        <p className="error-note" role="alert">
          {voice.failure.title} {voice.failure.detail}
        </p>
      )}

      <IdeaList
        ideas={ideas}
        onPick={(idea) => void build(`${idea.title}. ${idea.text}`)}
      />
    </div>
  );
}

function IdeaList({
  ideas,
  onPick,
}: {
  ideas: Ideas;
  onPick: (idea: Idea) => void;
}) {
  if (ideas.state === "error") return null;
  if (ideas.state === "loading") {
    return (
      <div className="ideas">
        <span className="lab">Looking for ideas in your last months…</span>
      </div>
    );
  }
  if (ideas.ideas.length === 0) return null;
  return (
    <div className="ideas">
      <span className="lab">Ideas from your last months</span>
      <div className="ideagrid">
        {ideas.ideas.map((idea) => (
          <button
            key={idea.title}
            type="button"
            className="idea"
            onClick={() => onPick(idea)}
          >
            <b>{idea.title}</b>
            <span className="num">{idea.text}</span>
            <SmallIcon name="arrow" />
          </button>
        ))}
      </div>
    </div>
  );
}
