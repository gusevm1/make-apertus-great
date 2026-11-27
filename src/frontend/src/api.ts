export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  provenance: { model: string; latency_ms: number } | null;
}

export interface ToolCall {
  id: string;
  message_id: string;
  title: string;
  error: string | null;
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
