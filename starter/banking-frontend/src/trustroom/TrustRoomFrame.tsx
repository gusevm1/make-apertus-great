/**
 * Embeds the team's solution (TRUSTROOM_URL) and speaks the postMessage protocol with it.
 * Security (docs §6): we post only to the TrustRoom origin, and accept messages only from that
 * origin *and* from our own iframe.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { config } from "../config";
import { isAppPath } from "../routes";
import { envelope, frameUrl, isEnvelope, type HostMessageType, type Mode } from "./protocol";
import styles from "./TrustRoom.module.css";
import { useTrustRoomActions } from "./TrustRoomProvider";
import { useTrustRoomContext } from "./useTrustRoomContext";

interface Props {
  mode: Mode;
  /** Panel open state; the iframe stays loaded while hidden. */
  visible: boolean;
  onClose?: () => void;
  /** "<board id>/<tile id>": the frame shows this one tile of the TrustRoom, as a dashboard widget. */
  tile?: string;
}

export function TrustRoomFrame({ mode, visible, onClose, tile }: Props) {
  const context = useTrustRoomContext(mode);
  // Wait for "today" so the initial query parameters are complete.
  if (!context.today) return null;
  return <Frame mode={mode} visible={visible} onClose={onClose} tile={tile} />;
}

function Frame({ mode, visible, onClose, tile }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);
  const context = useTrustRoomContext(mode);
  const { subscribe } = useTrustRoomActions();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const origin = new URL(config.trustroomUrl, window.location.href).origin;
  // Computed once: changing `src` would reload the solution. Later changes go via postMessage.
  const [src] = useState(() => {
    const url = new URL(frameUrl(config.trustroomUrl, context));
    if (tile) url.searchParams.set("tile", tile);
    return url.toString();
  });

  // The message handler reads the latest context without re-subscribing on every change.
  const latest = useRef({ context, onClose });
  useEffect(() => {
    latest.current = { context, onClose };
  });

  const post = useCallback(
    (type: HostMessageType, payload: object) =>
      iframeRef.current?.contentWindow?.postMessage(envelope(type, payload), origin),
    [origin],
  );

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.origin !== origin || event.source !== iframeRef.current?.contentWindow) return;
      if (!isEnvelope(event.data)) return;
      const { type, payload } = event.data;
      switch (type) {
        case "ready":
          // The context effect below sends the first context once `ready` is set.
          setReady(true);
          break;
        case "request-context":
          post("context", latest.current.context);
          break;
        case "navigate":
          if (isAppPath(payload.path)) navigate(payload.path);
          break;
        case "widgets-changed":
          queryClient.invalidateQueries({ queryKey: ["dashboards"] });
          break;
        case "close":
          if (mode === "panel") latest.current.onClose?.();
          break;
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [origin, mode, navigate, queryClient, post]);

  const contextKey = JSON.stringify(context);
  useEffect(() => {
    if (ready) post("context", JSON.parse(contextKey));
  }, [ready, contextKey, post]);

  useEffect(() => {
    if (ready && mode === "panel") post("visibility", { visible });
  }, [ready, mode, visible, post]);

  useEffect(() => subscribe((type, payload) => ready && post(type, payload)), [subscribe, ready, post]);

  return (
    <iframe
      ref={iframeRef}
      className={styles.frame}
      title="TrustRoom"
      src={src}
      allow="microphone; clipboard-read; clipboard-write"
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
    />
  );
}
