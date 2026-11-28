import { type ReactNode, useState } from "react";
import { fullDate, money } from "../board/format";
import { SmallIcon } from "../board/icons";
import type { ToolCall } from "../api";
import { Markdown } from "../lib/markdown";
import { AnswerTrace } from "./AnswerTrace";
import { checkFailure, decides } from "./checks";
import { CheckIcon } from "./icons";
import { MemoryCard } from "./MemoryCard";
import {
  type ChatMessage,
  type ContextEntry,
  didLinesOf,
  type FigureSource,
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
  const [openFigure, setOpenFigure] = useState<FigureSource | null>(null);
  const figures = provenance?.figures ?? [];
  const proposal = calls
    .filter((call) => call.tool_name === PROPOSE_TOOL && call.error === null)
    .map((call) => proposals.find((entry) => entry.id === call.result?.id))
    .find((entry) => entry !== undefined);
  return (
    <div className="bot">
      <Markdown
        text={text}
        plain={
          figures.length === 0
            ? undefined
            : (part) =>
                withFigures({
                  text: part,
                  figures,
                  open: openFigure,
                  onToggle: (figure) =>
                    setOpenFigure(figure === openFigure ? null : figure),
                })
        }
      />
      {openFigure !== null && (
        <FigureCard figure={openFigure} onClose={() => setOpenFigure(null)} />
      )}
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
  const deciding = checks.filter((check) => decides(check.name));
  const failedCheck = deciding.find(
    (check) =>
      !check.passed && (check.name !== "tool_calls_valid" || hasFailedCall),
  );
  const model = /apertus/i.test(provenance.model)
    ? "Apertus"
    : provenance.model;
  const figures = provenance.figures ?? [];
  const parts = [model];
  if (figures.length > 0) parts.push("tap a figure to see where it comes from");
  if (failedCheck !== undefined) parts.push(checkFailure(failedCheck.name));
  else if (deciding.length > 0)
    parts.push(
      `${deciding.length} ${deciding.length === 1 ? "check" : "checks"} passed`,
    );
  // Only web addresses become rows, each page once; the list comes from a search result.
  const pages = [
    ...new Map(
      provenance.sources
        .filter((source) => source.url?.startsWith("http") === true)
        .map((source) => [source.url, source]),
    ).values(),
  ];
  return (
    <>
      <span className="meta">{parts.join(" · ")}</span>
      {pages.length > 0 && (
        <div className="pages" aria-label="Web pages this answer used">
          {pages.map((page) => (
            <PageLink key={page.id} url={page.url ?? ""} title={page.title} />
          ))}
        </div>
      )}
    </>
  );
}

/** A web page as one row: its host, then its title. */
function PageLink({ url, title }: { url: string; title: string }) {
  return (
    <a className="page" href={url} target="_blank" rel="noreferrer">
      <b>{new URL(url).hostname.replace(/^www\./, "")}</b>
      <span>{title}</span>
      <SmallIcon name="arrow" size={12} />
    </a>
  );
}

// A figure is matched as a whole number: 50.00 is not the end of 150.00.
function withFigures({
  text,
  figures,
  open,
  onToggle,
}: {
  text: string;
  figures: FigureSource[];
  open: FigureSource | null;
  onToggle: (figure: FigureSource) => void;
}): ReactNode[] {
  const byText = new Map(figures.map((figure) => [figure.text, figure]));
  const pattern = new RegExp(
    `(?<![\\d'’.,])(${[...byText.keys()]
      .sort((first, second) => second.length - first.length)
      .map((figure) => figure.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      .join("|")})(?![\\d])`,
    "g",
  );
  const nodes: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const figure = byText.get(match[0]);
    if (figure === undefined) continue;
    if (match.index > last) nodes.push(text.slice(last, match.index));
    nodes.push(
      <button
        key={match.index}
        type="button"
        className="fig"
        aria-expanded={figure === open}
        aria-label={`${match[0]}: where it comes from`}
        onClick={() => onToggle(figure)}
      >
        {match[0]}
      </button>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** What one figure is, and the bookings or the page behind it. */
function FigureCard({
  figure,
  onClose,
}: {
  figure: FigureSource;
  onClose: () => void;
}) {
  const more = figure.count - figure.rows.length;
  return (
    <div className="figcard">
      <header>
        <span>
          <b>{figure.text}</b>
          <small>{figure.label}</small>
        </span>
        <button type="button" aria-label="Close" onClick={onClose}>
          <SmallIcon name="close" size={10} />
        </button>
      </header>
      {figure.url !== null && (
        <PageLink url={figure.url} title={figure.label} />
      )}
      {figure.rows.length > 0 && (
        <>
          <p className="from">
            {figure.count === 1 ? "1 booking" : `${figure.count} bookings`}
          </p>
          <ol className="figrows">
            {figure.rows.map((row) => (
              <li key={row.id}>
                <time dateTime={row.date ?? undefined}>
                  {row.date === null ? "" : fullDate(row.date)}
                </time>
                <span>{row.text}</span>
                <b>
                  {row.amount_chf === null ? "" : money(Number(row.amount_chf))}
                </b>
              </li>
            ))}
            {more > 0 && <li className="more">and {more} more</li>}
          </ol>
        </>
      )}
      {figure.url === null && figure.rows.length === 0 && (
        <p className="from">From {figure.label}.</p>
      )}
    </div>
  );
}
