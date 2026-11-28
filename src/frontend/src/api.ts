export interface DocumentRef {
  id: string;
  name: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  documents: DocumentRef[];
  provenance: {
    model: string;
    latency_ms: number;
    sources: { id: string; title: string; url: string | null }[];
  } | null;
}

export interface ToolCall {
  id: string;
  message_id: string;
  tool_name: string;
  title: string;
  round: number;
  plan: string;
  reason: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  /** The model that decided the call and how long the decision took; "server" for a rule. */
  provenance: { model: string; latency_ms: number } | null;
}

/** One version of a widget, drawn by the server from its stored spec and data. */
export interface WidgetVersion {
  widget_id: string;
  number: number;
  title: string;
  html: string;
  model: string | null;
  latency_ms: number;
  checks: { name: string; passed: boolean; detail: string | null }[];
  /** The version the customer's e-banking dashboard shows, or null. */
  published_version: number | null;
}

export interface WidgetPublication {
  widget_id: string;
  version_number: number;
  dashboard_id: string;
  dashboard_widget_id: string;
}

export interface Conversation {
  id: string;
  title: string | null;
}

export type FailureKind = "connection" | "apertus" | "other";

/** A failure as the chat shows it: what failed, and what became of the customer's input. */
export interface Failure {
  title: string;
  detail: string;
}

/** A failed request, with a message in our words instead of the browser's. */
export class RequestError extends Error {
  kind: FailureKind;

  constructor(kind: FailureKind, message: string) {
    super(message);
    this.kind = kind;
  }
}

export const CONNECTION_DROPPED = "The connection to the TrustRoom dropped.";
const APERTUS_DOWN = "Apertus is not answering right now.";
const UNKNOWN_FAILURE = "Something went wrong.";
// The other services whose 502 names them; every other 502 comes from Apertus.
const OTHER_SERVICES = /OCR|banking API|Web search/;

/** Calls our backend as the customer the e-banking token belongs to. */
export async function api<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  try {
    const response = await fetch(path, {
      ...init,
      headers: { ...init.headers, Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw await failureOf(response);
    return response.status === 204 ? (undefined as T) : await response.json();
  } catch (error) {
    throw requestErrorOf(error);
  }
}

/** Any failure as a RequestError; the browser reports a dropped connection as a TypeError. */
export function requestErrorOf(error: unknown): RequestError {
  if (error instanceof RequestError) return error;
  if (error instanceof TypeError) {
    return new RequestError("connection", CONNECTION_DROPPED);
  }
  return new RequestError("other", UNKNOWN_FAILURE);
}

export async function failureOf(response: Response): Promise<RequestError> {
  const isJson =
    response.headers.get("content-type")?.includes("application/json") === true;
  // Only our backend answers in JSON; a proxy that cannot reach it answers in text or HTML.
  if (!isJson) {
    return response.status >= 500
      ? new RequestError("connection", CONNECTION_DROPPED)
      : new RequestError("other", UNKNOWN_FAILURE);
  }
  return backendErrorOf(await response.json());
}

/** Our backend's error body, from a response or a stream `error` event. */
export function backendErrorOf(body: {
  error: string;
  message: string;
}): RequestError {
  if (body.error === "upstream_error" && !OTHER_SERVICES.test(body.message)) {
    return new RequestError("apertus", APERTUS_DOWN);
  }
  return new RequestError("other", body.message);
}

export function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
