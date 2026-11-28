import { Fragment, type ReactNode } from "react";

const HEADING = /^#{1,6}\s+(.*)$/;
// Apertus also starts items with – or •; a lone marker line has no text.
const ITEM = /^(\s*)(?:[-*+–•]|(\d+)[.)])(?:\s+(.*))?$/;
const FENCE = /^\s*```/;
// Code, http(s) link, bold, italic. A link to any other scheme stays text.
const INLINE =
  /`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+|#[a-z-]+)\)|\*\*(.+?)\*\*|__(.+?)__|(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])|(?<!\w)_(?![\s_])(.+?)(?<![\s_])_(?!\w)/g;

type Item = { text: string; children: List | null };
type List = { isOrdered: boolean; start: number; items: Item[] };

// Only React elements are made from the text, so HTML in a model answer stays text.
export function Markdown({ text }: { text: string }) {
  return <div className="markdown">{blocksOf(text)}</div>;
}

function blocksOf(text: string): ReactNode[] {
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: List | null = null;
  let code: string[] | null = null;

  function flushParagraph() {
    if (paragraph.length === 0) return;
    blocks.push(
      <p key={blocks.length}>
        {paragraph.map((line, index) => (
          <Fragment key={index}>
            {index > 0 && <br />}
            {inlineOf(line)}
          </Fragment>
        ))}
      </p>,
    );
    paragraph = [];
  }

  function flushList() {
    if (list === null) return;
    blocks.push(listOf(list, blocks.length));
    list = null;
  }

  function flushCode() {
    if (code === null) return;
    blocks.push(
      <pre key={blocks.length}>
        <code>{code.join("\n")}</code>
      </pre>,
    );
    code = null;
  }

  // ponytail: one level of nesting, deeper items join that level
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const isFence = FENCE.test(line);
    if (code !== null) {
      if (isFence) flushCode();
      else code.push(line);
      continue;
    }
    const heading = HEADING.exec(line);
    const item = ITEM.exec(line);
    if (isFence) {
      flushParagraph();
      flushList();
      code = [];
    } else if (line === "") {
      // A blank line between items keeps the list together.
      flushParagraph();
    } else if (heading !== null) {
      flushParagraph();
      flushList();
      blocks.push(
        <p key={blocks.length}>
          <strong>{inlineOf(heading[1])}</strong>
        </p>,
      );
    } else if (item !== null) {
      const [, indent, number, itemText] = item;
      if (itemText === undefined) continue;
      const entry = {
        isOrdered: number !== undefined,
        start: Number(number ?? 1),
      };
      const parent = list?.items.at(-1);
      if (indent.length >= 2 && parent !== undefined) {
        parent.children ??= { ...entry, items: [] };
        parent.children.items.push({ text: itemText, children: null });
        continue;
      }
      flushParagraph();
      if (list !== null && list.isOrdered !== entry.isOrdered) flushList();
      list ??= { ...entry, items: [] };
      list.items.push({ text: itemText, children: null });
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  // A fence still open while the answer streams shows what has arrived.
  flushCode();
  return blocks;
}

function listOf(list: List, key: number): ReactNode {
  const items = list.items.map((item, index) => (
    <li key={index}>
      {inlineOf(item.text)}
      {item.children !== null && listOf(item.children, 0)}
    </li>
  ));
  if (!list.isOrdered) return <ul key={key}>{items}</ul>;
  return (
    <ol key={key} start={list.start}>
      {items}
    </ol>
  );
}

// The TrustRoom views a chat answer may link to.
const IN_PAGE_LINK = /^#categories$/;

function inlineOf(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const [, code, label, url, bold, boldUnderscore, italic, italicUnderscore] =
      match;
    const key = match.index;
    if (code !== undefined) nodes.push(<code key={key}>{code}</code>);
    else if (url !== undefined && IN_PAGE_LINK.test(url))
      // A link to a view of the TrustRoom itself, like #categories, stays in this frame.
      nodes.push(
        <a key={key} href={url}>
          {inlineOf(label)}
        </a>,
      );
    else if (url !== undefined && URL.canParse(url))
      // The host is shown, so a label like "your e-banking" cannot hide where the link goes.
      nodes.push(
        <Fragment key={key}>
          <a href={url} target="_blank" rel="noreferrer">
            {inlineOf(label)}
          </a>{" "}
          <span className="link-host">({new URL(url).hostname})</span>
        </Fragment>,
      );
    else if (url !== undefined) nodes.push(match[0]);
    else if (bold !== undefined || boldUnderscore !== undefined)
      nodes.push(<strong key={key}>{inlineOf(bold ?? boldUnderscore)}</strong>);
    else nodes.push(<em key={key}>{inlineOf(italic ?? italicUnderscore)}</em>);
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
