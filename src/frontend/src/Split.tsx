import {
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";

/** The board's share of the screen when both sides show. */
export const SPLIT = 0.62;
// Let go this close to an edge and that side closes.
const SNAP = 0.14;
const NARROW = "(max-width: 860px)";

/** Board and chat on one screen: `share` is the board's part, 1 is only the board, 0 only the chat. */
export function Split({
  share,
  onShare,
  board,
  chat,
}: {
  share: number;
  onShare: (share: number) => void;
  board: ReactNode;
  chat: ReactNode;
}) {
  const stage = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragShare, setDragShare] = useState<number | null>(null);
  const isNarrow = useMatches(NARROW);
  const shown = dragShare ?? share;

  function drag(event: PointerEvent<HTMLDivElement>) {
    if (!isDragging || stage.current === null) return;
    const box = stage.current.getBoundingClientRect();
    const position = isNarrow
      ? (event.clientY - box.top) / box.height
      : (event.clientX - box.left) / box.width;
    setDragShare(Math.min(1, Math.max(0, position)));
  }

  function drop() {
    setIsDragging(false);
    if (dragShare === null) return;
    setDragShare(null);
    if (dragShare < SNAP) return onShare(0);
    if (dragShare > 1 - SNAP) return onShare(1);
    onShare(dragShare);
  }

  // The arrows step from only the board to both to only the chat.
  function step(event: KeyboardEvent<HTMLDivElement>) {
    const towardsChat = isNarrow ? "ArrowUp" : "ArrowLeft";
    const towardsBoard = isNarrow ? "ArrowDown" : "ArrowRight";
    if (event.key === towardsChat) onShare(share === 1 ? SPLIT : 0);
    if (event.key === towardsBoard) onShare(share === 0 ? SPLIT : 1);
  }

  return (
    <div
      ref={stage}
      className="split"
      data-dragging={isDragging ? "" : undefined}
    >
      <div
        className="pane boardpane"
        style={{ flexBasis: `${shown * 100}%` }}
        data-closed={shown === 0 ? "" : undefined}
        inert={shown === 0}
      >
        {board}
      </div>
      <div
        className="handle"
        role="separator"
        tabIndex={0}
        aria-orientation={isNarrow ? "horizontal" : "vertical"}
        aria-label="Room for the board and the chat"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(shown * 100)}
        data-hidden={shown === 0 || shown === 1 ? "" : undefined}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          setIsDragging(true);
        }}
        onPointerMove={drag}
        onPointerUp={drop}
        onPointerCancel={drop}
        onDoubleClick={() => onShare(SPLIT)}
        onKeyDown={step}
      />
      <div
        className="pane chatpane"
        data-closed={shown === 1 ? "" : undefined}
        inert={shown === 1}
      >
        {chat}
      </div>
    </div>
  );
}

function useMatches(query: string) {
  const [matches, setMatches] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const media = matchMedia(query);
    const update = () => setMatches(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}
