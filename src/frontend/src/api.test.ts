import { afterEach, expect, test, vi } from "vitest";
import { api, backendErrorOf } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function answerWith(response: Response) {
  vi.stubGlobal("fetch", async () => response);
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("a stopped backend reads as a dropped connection, not the browser's text", async () => {
  vi.stubGlobal("fetch", async () => {
    throw new TypeError("NetworkError when attempting to fetch resource.");
  });

  await expect(api("/api/conversations", "token")).rejects.toMatchObject({
    kind: "connection",
    message: "The connection to the TrustRoom dropped.",
  });
});

test("a proxy's own 502 page reads as a dropped connection", async () => {
  answerWith(new Response("<html>Bad Gateway</html>", { status: 502 }));

  await expect(api("/api/conversations", "token")).rejects.toMatchObject({
    kind: "connection",
  });
});

test("a 502 from Apertus says Apertus is not answering", async () => {
  answerWith(
    jsonResponse(502, {
      error: "upstream_error",
      message: "Apertus timed out",
    }),
  );

  await expect(api("/api/transcriptions", "token")).rejects.toMatchObject({
    kind: "apertus",
    message: "Apertus is not answering right now.",
  });
});

test("a 502 from another service keeps the backend's message", async () => {
  answerWith(
    jsonResponse(502, {
      error: "upstream_error",
      message: "The OCR service is unreachable",
    }),
  );

  await expect(api("/api/documents", "token")).rejects.toMatchObject({
    kind: "other",
    message: "The OCR service is unreachable",
  });
});

test("a stream error event from Apertus says Apertus is not answering", () => {
  const error = backendErrorOf({
    error: "upstream_error",
    message: "Apertus stream ended without a result",
  });

  expect(error.kind).toBe("apertus");
});
