import type { ReactNode } from "react";

const HEADING = /^#{1,6}\s+(.*)$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
// Code, http(s) link, bold, italic. A link to any other scheme stays text.
const INLINE =
  /`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*(.+?)\*\*|__(.+?)__|(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])|(?<!\w)_(?![\s_])(.+?)(?<![\s_])_(?!\w)/g;

type List = { isOrdered: boolean; start: number; items: string[] };

/** Model text as formatting. Only React elements are made, so HTML in the text stays text. */
export function Markdown({ text }: { text: string }) {
  return <div className="markdown">{blocksOf(text)}</div>;
}

function blocksOf(text: string): ReactNode[] {
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: List | null = null;

  function flush() {
    if (paragraph.length > 0) {
      blocks.push(
        <p key={blocks.length}>
          {paragraph.flatMap((line, index) => [
            index > 0 && <br key={`br${index}`} />,
            ...inlineOf(line),
          ])}
        </p>,
      );
      paragraph = [];
    }
    if (list !== null) {
      const items = list.items.map((item, index) => (
        <li key={index}>{inlineOf(item)}</li>
      ));
      blocks.push(
        list.isOrdered ? (
          <ol key={blocks.length} start={list.start}>
            {items}
          </ol>
        ) : (
          <ul key={blocks.length}>{items}</ul>
        ),
      );
      list = null;
    }
  }

  // ponytail: nested lists come out flat, indent them when answers need it
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const heading = HEADING.exec(line);
    const numbered = NUMBERED.exec(line);
    const item = numbered?.[2] ?? BULLET.exec(line)?.[1];
    if (line.trim() === "") {
      flush();
    } else if (heading !== null) {
      flush();
      blocks.push(
        <p key={blocks.length}>
          <strong>{inlineOf(heading[1])}</strong>
        </p>,
      );
    } else if (item !== undefined) {
      const isOrdered = numbered !== null;
      if (
        paragraph.length > 0 ||
        (list !== null && list.isOrdered !== isOrdered)
      )
        flush();
      if (list === null) {
        list = {
          isOrdered,
          start: numbered === null ? 1 : Number(numbered[1]),
          items: [],
        };
      }
      list.items.push(item);
    } else {
      if (list !== null) flush();
      paragraph.push(line);
    }
  }
  flush();
  return blocks;
}

function inlineOf(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const [, code, label, url, bold, boldUnderscore, italic, italicUnderscore] =
      match;
    const key = match.index;
    if (code !== undefined) nodes.push(<code key={key}>{code}</code>);
    else if (url !== undefined)
      nodes.push(
        <a key={key} href={url} target="_blank" rel="noreferrer">
          {inlineOf(label)}
        </a>,
      );
    else if (bold !== undefined || boldUnderscore !== undefined)
      nodes.push(<strong key={key}>{inlineOf(bold ?? boldUnderscore)}</strong>);
    else nodes.push(<em key={key}>{inlineOf(italic ?? italicUnderscore)}</em>);
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
