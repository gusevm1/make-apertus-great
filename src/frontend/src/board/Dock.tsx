import { type KeyboardEvent, useState } from "react";
import { SmallIcon } from "./icons";
import type { BoardSummary } from "./types";

const NAME_MAX_LENGTH = 80;

/** The boards as tabs along the bottom, the open one dark, and "+" for a new one. */
export function Dock({
  boards,
  openId,
  isNewOpen,
  onOpen,
  onNew,
  onRename,
  onDelete,
}: {
  boards: BoardSummary[];
  openId: string | null;
  isNewOpen: boolean;
  onOpen: (boardId: string) => void;
  onNew: () => void;
  onRename: (boardId: string, name: string) => void;
  onDelete: (boardId: string) => void;
}) {
  const [renaming, setRenaming] = useState<{
    id: string;
    draft: string;
  } | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [isDeleteArmed, setIsDeleteArmed] = useState(false);
  const menuBoard = boards.find((board) => board.id === menuFor);

  function startRename(board: BoardSummary) {
    setMenuFor(null);
    setRenaming({ id: board.id, draft: board.name });
  }

  function saveName() {
    if (renaming === null) return;
    const name = renaming.draft.trim().slice(0, NAME_MAX_LENGTH);
    const board = boards.find((other) => other.id === renaming.id);
    setRenaming(null);
    if (board !== undefined && name !== "" && name !== board.name)
      onRename(board.id, name);
  }

  function handleNameKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") saveName();
    if (event.key === "Escape") setRenaming(null);
  }

  function toggleMenu(boardId: string) {
    setIsDeleteArmed(false);
    setMenuFor((current) => (current === boardId ? null : boardId));
  }

  return (
    <div className="dockwrap">
      <nav className="dock" aria-label="Your boards">
        {boards.map((board) => {
          const isOpen = board.id === openId && !isNewOpen;
          if (renaming?.id === board.id) {
            return (
              <input
                key={board.id}
                className="tabname"
                aria-label="Name of the board"
                value={renaming.draft}
                maxLength={NAME_MAX_LENGTH}
                size={Math.max(8, renaming.draft.length)}
                autoFocus
                onChange={(event) =>
                  setRenaming({ id: board.id, draft: event.target.value })
                }
                onKeyDown={handleNameKey}
                onBlur={saveName}
              />
            );
          }
          return (
            <span key={board.id} className={isOpen ? "tab on" : "tab"}>
              <button
                type="button"
                aria-current={isOpen ? "page" : undefined}
                title={isOpen ? "Double-click to rename" : undefined}
                onClick={() => {
                  setMenuFor(null);
                  onOpen(board.id);
                }}
                onDoubleClick={() => startRename(board)}
              >
                {board.name}
              </button>
              {isOpen && (
                <button
                  type="button"
                  className="more"
                  aria-label={`More for ${board.name}`}
                  aria-expanded={menuFor === board.id}
                  onClick={() => toggleMenu(board.id)}
                >
                  <SmallIcon name="more" />
                </button>
              )}
            </span>
          );
        })}
        {isNewOpen && (
          <span className="tab on">
            <button type="button" aria-current="page">
              New board
            </button>
          </span>
        )}
        <button
          type="button"
          className="plus"
          aria-label="New board"
          onClick={() => {
            setMenuFor(null);
            onNew();
          }}
        >
          <SmallIcon name="plus" />
        </button>
      </nav>
      {menuBoard !== undefined && (
        <div className="dockmenu" role="menu" aria-label={menuBoard.name}>
          <button
            type="button"
            role="menuitem"
            onClick={() => startRename(menuBoard)}
          >
            <SmallIcon name="rename" />
            Rename
          </button>
          {isDeleteArmed ? (
            <button
              type="button"
              role="menuitem"
              className="danger"
              onClick={() => {
                setMenuFor(null);
                onDelete(menuBoard.id);
              }}
            >
              <SmallIcon name="remove" />
              Delete “{menuBoard.name}” for good
            </button>
          ) : (
            <button
              type="button"
              role="menuitem"
              onClick={() => setIsDeleteArmed(true)}
            >
              <SmallIcon name="remove" />
              Delete board
            </button>
          )}
        </div>
      )}
    </div>
  );
}
