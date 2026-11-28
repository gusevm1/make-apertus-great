import "@fontsource-variable/geist";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { TileWidget } from "./board/TileWidget";
import "./tokens.css";
import "./styles.css";
import "./board/board.css";
import "./chat/chat.css";
import "./profile/profile.css";

// "<board id>/<tile id>": the e-banking dashboard frames this one tile as a widget.
const tile = new URLSearchParams(location.search).get("tile")?.split("/");
if (tile !== undefined) document.documentElement.classList.add("tile-widget");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {tile === undefined ? (
      <App />
    ) : (
      <TileWidget boardId={tile[0]} tileId={tile[1]} />
    )}
  </StrictMode>,
);
