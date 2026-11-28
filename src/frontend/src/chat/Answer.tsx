import type { ReactNode } from "react";
import type { ToolCall } from "../api";
import { Markdown } from "../lib/markdown";
import { AnswerTrace } from "./AnswerTrace";
import { CheckIcon } from "./icons";
import { MemoryCard } from "./MemoryCard";
import {
  type ChatMessage,
  type ContextEntry,
  didLinesOf,
  PROPOSE_TOOL,
} from "./types";

/** One stored answer: its text, what it did to the boards, a proposal, and where its figures come from. */
export function Answer({
  token,
  text,
  calls,
  provenance,
  proposals,
  onOpenBoard,
}: {
  token: string;
  text: string;
  calls: ToolCall[];
  provenance: ChatMessage["provenance"];
  proposals: ContextEntry[];
  onOpenBoard: (boardId: string) => void;
}) {
  const did = didLinesOf(calls);
  // A refused note proposal is the server's own business, not a failure the customer has to read.
  const failed = calls.filter(
    (call) => call.error !== null && call.tool_name !== PROPOSE_TOOL,
  );
  const proposal = calls
    .filter((call) => call.tool_name === PROPOSE_TOOL && call.error === null)
    .map((call) => proposals.find((entry) => entry.id === call.result?.id))
    .find((entry) => entry !== undefined);
  return (
    <div className="bot">
      <Markdown text={text} />
      {(did.length > 0 || failed.length > 0) && (
        <div className="did">
          {did.map((line) => (
            <div key={line.id}>
              <span className="tick">
                <CheckIcon />
              </span>
              {line.text}
              {line.openBoardId !== null && (
                <OpenLink
                  boardId={line.openBoardId}
                  onOpenBoard={onOpenBoard}
                />
              )}
            </div>
          ))}
          {failed.map((call) => (
            <div key={call.id}>
              {call.title}: {call.error}
            </div>
          ))}
        </div>
      )}
      {proposal !== undefined && (
        <MemoryCard token={token} entryId={proposal.id} text={proposal.text} />
      )}
      {provenance !== null && (
        <Meta provenance={provenance} hasFailedCall={failed.length > 0} />
      )}
      {(calls.length > 0 || provenance !== null) && (
        <AnswerTrace calls={calls} provenance={provenance} isLive={false} />
      )}
    </div>
  );
}

function OpenLink({
  boardId,
  onOpenBoard,
}: {
  boardId: string;
  onOpenBoard: (boardId: string) => void;
}) {
  return (
    <a
      href={`#${boardId}`}
      onClick={(event) => {
        event.preventDefault();
        onOpenBoard(boardId);
      }}
    >
      Open
    </a>
  );
}

function Meta({
  provenance,
  hasFailedCall,
}: {
  provenance: NonNullable<ChatMessage["provenance"]>;
  hasFailedCall: boolean;
}) {
  const checks = provenance.checks ?? [];
  const failedCheck = checks.find(
    (check) =>
      !check.passed && (check.name !== "tool_calls_valid" || hasFailedCall),
  );
  const model = /apertus/i.test(provenance.model)
    ? "Apertus"
    : provenance.model;
  let note = "every figure comes from your bookings";
  if (failedCheck !== undefined)
    note = `a check did not pass: ${failedCheck.name}`;
  else if (checks.length > 0)
    note += `, ${checks.length} ${checks.length === 1 ? "check" : "checks"} passed`;
  const links: ReactNode[] = provenance.sources
    // Only web addresses become links; the list comes from a search result.
    .filter((source) => source.url?.startsWith("http") === true)
    .map((source) => (
      <a
        key={source.id}
        href={source.url ?? ""}
        target="_blank"
        rel="noreferrer"
      >
        {source.title}
      </a>
    ));
  return (
    <span className="meta">
      {model} · {note}
      {links.length > 0 && <> · {links}</>}
    </span>
  );
}
