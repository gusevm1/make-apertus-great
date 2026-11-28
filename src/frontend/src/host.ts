import { useEffect, useState } from "react";

/** What the e-banking tells us about where the customer is (starter/docs/trustroom-panel-context.md §4). */
export interface HostContext {
  mode: "panel" | "fullpage";
  page: { id: string; path: string; title: string };
  account: { account_id: string; iban: string; name: string } | null;
  dashboard_id: string | null;
  customer: {
    customer_id: string;
    first_name: string;
    last_name: string;
  } | null;
  today: string;
  access_token: string;
}

type OutgoingType =
  "ready" | "request-context" | "navigate" | "widgets-changed" | "close";

// The e-banking that embeds us. We only talk to, and listen to, that origin.
const HOST_ORIGIN = new URL(document.referrer || location.href).origin;

/** Sends one message of the TrustRoom protocol to the e-banking. */
export function sendToHost(
  type: OutgoingType,
  payload: Record<string, unknown> = {},
) {
  window.parent.postMessage(
    { protocol: "trustroom", version: 1, type, payload },
    HOST_ORIGIN,
  );
}

// The last context the e-banking sent, so a panel that mounts later starts with it.
let lastContext: HostContext | null = null;

/** The current context from the e-banking, or null until it has answered the handshake. */
export function useHostContext(): HostContext | null {
  const [context, setContext] = useState<HostContext | null>(lastContext);

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== HOST_ORIGIN || event.data?.protocol !== "trustroom")
        return;
      if (event.data.type !== "context") return;
      lastContext = event.data.payload;
      setContext(event.data.payload);
    }
    window.addEventListener("message", handleMessage);
    // The host answers only the first `ready`; after a reload inside the iframe we have to ask.
    sendToHost("ready");
    sendToHost("request-context");
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  return context;
}
