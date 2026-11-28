import { useState } from "react";
import { api, json, requestErrorOf } from "../api";
import { BookmarkIcon } from "./icons";
import { NOTES_CHANGED } from "./types";

type Answer = "idle" | "sending" | "saved" | "dismissed";

/** The chat's proposal for the profile: the customer saves it or declines. */
export function MemoryCard({
  token,
  entryId,
  text,
}: {
  token: string;
  entryId: string;
  text: string;
}) {
  const [answer, setAnswer] = useState<Answer>("idle");
  const [failure, setFailure] = useState<string | null>(null);

  async function respond(status: "active" | "dismissed") {
    setAnswer("sending");
    setFailure(null);
    try {
      await api(`/api/context-entries/${entryId}`, token, {
        ...json({ status }),
        method: "PATCH",
      });
      setAnswer(status === "active" ? "saved" : "dismissed");
      if (status === "active") window.dispatchEvent(new Event(NOTES_CHANGED));
    } catch (error) {
      setFailure(requestErrorOf(error).message);
      setAnswer("idle");
    }
  }

  if (answer === "dismissed") return null;
  if (answer === "saved")
    return <span className="meta">Saved to your profile</span>;
  return (
    <div className="mem">
      <span className="k">
        <BookmarkIcon />
        Remember this for next time?
      </span>
      <p>{text}</p>
      {failure !== null && (
        <p className="error-note" role="alert">
          {failure}
        </p>
      )}
      <div className="acts">
        <button
          className="btn go"
          type="button"
          disabled={answer === "sending"}
          onClick={() => void respond("active")}
        >
          Save to my profile
        </button>
        <button
          className="btn"
          type="button"
          disabled={answer === "sending"}
          onClick={() => void respond("dismissed")}
        >
          Not now
        </button>
      </div>
    </div>
  );
}
