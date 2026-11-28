import { useState } from "react";
import { Chat, FLAGS, FlagList, Header, Tiles } from "./shared";

/** B: a bell with a count in the TrustRoom header; the list opens under it. */
export function VariantB() {
  const [open, setOpen] = useState(true);
  return (
    <div className="m-page">
      <Header
        extra={
          <span className="b-wrap">
            <button
              className="b-bell"
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M4 11V7a4 4 0 0 1 8 0v4l1 1.5H3Z M6.5 14h3" />
              </svg>
              <span className="b-count">{FLAGS.length}</span>
            </button>
            {open && (
              <div className="b-pop">
                <h2>Needs attention</h2>
                <FlagList />
              </div>
            )}
          </span>
        }
      />
      <div className="m-body">
        <main className="m-board">
          <Tiles />
        </main>
        <Chat />
      </div>
    </div>
  );
}
