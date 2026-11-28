import { useState } from "react";
import { SmallIcon } from "../../board/icons";
import { Chat, FLAGS, FlagList, Header, Tiles } from "./shared";

/** A + B: the box above the board on open; Hide folds it to one quiet line, remembered. */
export function VariantD() {
  const [folded, setFolded] = useState(false);
  return (
    <div className="m-page">
      <Header />
      <div className="m-body">
        <main className="m-board">
          {folded ? (
            <button className="d-line" onClick={() => setFolded(false)}>
              <span className="b-count">{FLAGS.length}</span>
              need attention
              <SmallIcon name="chevron" size={10} />
            </button>
          ) : (
            <section className="f-box">
              <header className="d-head">
                <h2>Needs attention</h2>
                <button className="f-link" onClick={() => setFolded(true)}>
                  Hide
                </button>
              </header>
              <FlagList />
            </section>
          )}
          <Tiles />
        </main>
        <Chat />
      </div>
    </div>
  );
}
