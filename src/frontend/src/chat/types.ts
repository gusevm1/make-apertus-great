import type { Message, ToolCall } from "../api";

export interface ChatMessage extends Omit<Message, "provenance"> {
  provenance:
    | (NonNullable<Message["provenance"]> & {
        checks?: { name: string; passed: boolean; detail: string | null }[];
      })
    | null;
}

export interface ConversationRef {
  id: string;
  title: string | null;
  created_at: string;
}

export interface ContextEntry {
  id: string;
  text: string;
  status: "proposed" | "active" | "dismissed" | "replaced";
}

export const NOTES_CHANGED = "trustroom:notes-changed";

export const BOARD_TOOLS = [
  "add_tile",
  "rename_tile",
  "move_tile",
  "remove_tile",
  "create_board",
  "rename_board",
];

export const PROPOSE_TOOL = "propose_context_entry";

export interface DidLine {
  id: string;
  text: string;
  /** Set on a created board, which gets an Open link. */
  openBoardId: string | null;
}

/** One line per successful board-tool call, from its result's `summary`. */
export function didLinesOf(calls: Pick<ToolCall, "id" | "tool_name" | "error" | "result">[]) {
  const lines: DidLine[] = [];
  for (const call of calls) {
    if (!BOARD_TOOLS.includes(call.tool_name) || call.error !== null) continue;
    const summary = call.result?.summary;
    if (typeof summary !== "string") continue;
    const boardId = call.result?.board_id;
    lines.push({
      id: call.id,
      text: summary,
      openBoardId:
        call.tool_name === "create_board" && typeof boardId === "string"
          ? boardId
          : null,
    });
  }
  return lines;
}

/** The id of the board this turn created, if any. */
export function createdBoardOf(calls: Pick<ToolCall, "tool_name" | "error" | "result">[]) {
  for (const call of calls) {
    const boardId = call.result?.board_id;
    if (
      call.tool_name === "create_board" &&
      call.error === null &&
      typeof boardId === "string"
    )
      return boardId;
  }
  return undefined;
}

export function ranBoardTool(calls: Pick<ToolCall, "tool_name" | "error">[]) {
  return calls.some(
    (call) => BOARD_TOOLS.includes(call.tool_name) && call.error === null,
  );
}
