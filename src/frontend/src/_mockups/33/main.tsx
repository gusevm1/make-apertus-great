import "@fontsource-variable/geist";
import { useState } from "react";
import { createRoot } from "react-dom/client";
import "../../tokens.css";
import "./mock.css";
import { VariantA } from "./VariantA";
import { VariantB } from "./VariantB";
import { VariantC } from "./VariantC";
import { VariantD } from "./VariantD";

const VARIANTS = {
  D: {
    view: VariantD,
    idea: "A, foldable. The box shows above the board on open. “Hide” folds it to one line, “4 need attention ›”, and the TrustRoom remembers that. A new flag unfolds it again.",
  },
  A: {
    view: VariantA,
    idea: "A “Needs attention” box above the board. You see it every time the TrustRoom opens, without clicking. At 440 px it sits above the first tile.",
  },
  B: {
    view: VariantB,
    idea: "A bell with a count in the TrustRoom header. The board stays as it is, and the list opens under the bell (shown open here).",
  },
  C: {
    view: VariantC,
    idea: "The flags head the chat column as a “Since your last visit” card above the conversation. At 440 px the panel opens on the board, so the card only shows on the Chat tab (here stacked under the board).",
  },
};

type Key = keyof typeof VARIANTS;

function Gallery() {
  const [key, setKey] = useState<Key>("D");
  const src = `/mockup-33.html?v=${key}`;
  return (
    <div className="g">
      <header className="g-head">
        <h1>#33 · where alerts show</h1>
        <nav>
          {(Object.keys(VARIANTS) as Key[]).map((other) => (
            <button
              key={other}
              aria-pressed={other === key}
              onClick={() => setKey(other)}
            >
              {other}
            </button>
          ))}
        </nav>
      </header>
      <p className="g-idea">
        <b>{key}:</b> {VARIANTS[key].idea}
      </p>
      <p className="g-scope">
        Same row in all three: kind, what, CHF figure, then Ask · Done · ⋯
        (Don't show again, Alert settings). Click a row for its bookings. Max 3,
        then “Show all”.
      </p>
      <div className="g-frames">
        <iframe
          key={`${key}-w`}
          title={`${key} full page`}
          src={src}
          className="g-wide"
        />
        <div>
          <iframe
            key={`${key}-n`}
            title={`${key} at 440 px`}
            src={src}
            className="g-narrow"
          />
          <p className="g-cap">440 px side panel</p>
        </div>
      </div>
    </div>
  );
}

const solo = new URLSearchParams(location.search).get("v") as Key | null;
const Solo = solo === null ? null : VARIANTS[solo].view;
createRoot(document.getElementById("root")!).render(
  Solo === null ? <Gallery /> : <Solo />,
);
