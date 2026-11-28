import { useState } from "react";
import { api, requestErrorOf } from "./api";

// Earlier versions of a note go with the note that replaced them.
const NOTE_STATUSES = ["active", "proposed", "dismissed"];

/** Deletes everything the list at `listPath` returns, one by one, so a failure names its request. */
async function removeAll(listPath: string, path: string, token: string) {
  const rows = await api<{ id: string }[]>(listPath, token);
  for (const row of rows)
    await api<void>(`${path}/${row.id}`, token, { method: "DELETE" });
}

/** Removes the boards, chats and notes the TrustRoom made for this customer; their documents stay. */
export function DemoReset({
  token,
  onDone,
}: {
  token: string;
  onDone: () => void;
}) {
  const [state, setState] = useState<"idle" | "armed" | "resetting">("idle");
  const [error, setError] = useState<string | null>(null);

  async function wipe() {
    setState("resetting");
    setError(null);
    try {
      // Boards first: a board takes its tiles and its chats along.
      await removeAll("/api/boards", "/api/boards", token);
      await removeAll("/api/conversations", "/api/conversations", token);
      for (const status of NOTE_STATUSES)
        await removeAll(
          `/api/context-entries?status=${status}`,
          "/api/context-entries",
          token,
        );
      onDone();
    } catch (error) {
      setError(requestErrorOf(error).message);
      setState("idle");
    }
  }

  let label = "Reset";
  if (state === "armed") label = "Reset?";
  else if (state === "resetting") label = "Resetting…";
  return (
    <>
      {error !== null && (
        <span className="reset-error" role="alert">
          Not everything was reset. {error}
        </span>
      )}
      <button
        type="button"
        className="reset"
        data-state={state}
        disabled={state === "resetting"}
        title="Delete the boards, chats and notes the TrustRoom made for this customer, and start again from the first visit"
        // The first click asks, the second resets; leaving the button takes the question back.
        onClick={() => (state === "armed" ? void wipe() : setState("armed"))}
        onBlur={() =>
          setState((current) => (current === "armed" ? "idle" : current))
        }
      >
        {label}
      </button>
    </>
  );
}
