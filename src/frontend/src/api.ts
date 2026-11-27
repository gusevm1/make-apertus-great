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

/** Calls our backend as the customer the e-banking token belongs to. */
export async function api<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(await failureMessage(response));
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function failureMessage(response: Response): Promise<string> {
  const isJson =
    response.headers.get("content-type")?.includes("application/json") === true;
  if (!isJson) return `The request failed (${response.status}).`;
  const body: { message: string } = await response.json();
  return body.message;
}

export function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
