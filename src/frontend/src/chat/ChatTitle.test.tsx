import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import { ChatTitle, renameOf } from "./ChatTitle";

test("a typed name is saved trimmed and cut at 60 characters", () => {
  expect(renameOf("  Japan trip  ", "Was kostet")).toEqual({
    action: "save",
    title: "Japan trip",
  });
  expect(renameOf("x".repeat(80), null)).toEqual({
    action: "save",
    title: "x".repeat(60),
  });
});

test("an empty or blank name is refused and never saved", () => {
  expect(renameOf("", "Japan trip")).toEqual({ action: "refuse" });
  expect(renameOf("   ", "Japan trip")).toEqual({ action: "refuse" });
});

test("the unchanged name closes the field without saving", () => {
  expect(renameOf("Japan trip ", "Japan trip")).toEqual({ action: "close" });
});

test("an open chat's name is a button that renames it", () => {
  const output = renderToStaticMarkup(
    <ChatTitle
      title="Japan trip"
      about="about no board"
      onRename={async () => undefined}
    />,
  );

  expect(output).toContain('<button type="button" title="Rename this chat">');
  expect(output).toContain("<b>Japan trip</b>");
  expect(output).toContain("<span>about no board</span>");
});

test("without an open chat the name is plain text", () => {
  const output = renderToStaticMarkup(
    <ChatTitle title={null} about="about no board" onRename={null} />,
  );

  expect(output).not.toContain("<button");
  expect(output).toContain("<b>New chat</b>");
});
