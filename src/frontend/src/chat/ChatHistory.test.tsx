import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import { HistoryRow } from "./ChatHistory";
import type { ConversationRef } from "./types";

const JAPAN: ConversationRef = {
  id: "chat-1",
  title: "Japan trip budget",
  board_id: null,
  created_at: "2026-11-20T09:30:00Z",
};

function row(step: "menu" | "rename" | "delete" | null) {
  return renderToStaticMarkup(
    <HistoryRow
      conversation={JAPAN}
      isActive={false}
      step={step}
      onStep={() => undefined}
      onPick={() => undefined}
      onRename={async () => undefined}
      onDelete={async () => undefined}
    />,
  );
}

test("a closed row opens the chat and offers ⋯ for renaming or deleting it", () => {
  const output = row(null);

  expect(output).toContain("<b>Japan trip budget</b>");
  expect(output).toContain('aria-label="Rename or delete Japan trip budget"');
  expect(output).toContain('aria-expanded="false"');
  expect(output).not.toContain(">Delete<");
});

test("⋯ shows Rename and Delete", () => {
  const output = row("menu");

  expect(output).toContain('aria-expanded="true"');
  expect(output).toContain(">Rename</button>");
  expect(output).toContain(">Delete</button>");
});

test("Rename turns the title into an input holding the current name", () => {
  const output = row("rename");

  expect(output).toContain('aria-label="New name for Japan trip budget"');
  expect(output).toContain('value="Japan trip budget"');
  expect(output).not.toContain("<b>Japan trip budget</b>");
});

test("Delete asks inside the row before anything is deleted", () => {
  const output = row("delete");

  expect(output).toContain("<span>Delete this chat?</span>");
  expect(output).toContain('class="danger"');
  expect(output).toContain(">Cancel</button>");
});
