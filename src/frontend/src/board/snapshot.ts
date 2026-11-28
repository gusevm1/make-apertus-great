/** A tile as a page of its own for the e-banking dashboard: the same markup under the same CSS. */

export interface TileSnapshot {
  html: string;
  height: number;
  columns: number;
}

// What a tile only carries while the customer works on it in the board.
const BOARD_ONLY_CLASSES = ["sel", "grow", "drop-target"];
// A dashboard column and the gap between two, at the e-banking's usual width.
const COLUMN_PX = 300;
const GAP_PX = 24;
// The tile fills its dashboard cell and brings no shadow, as the cards around it have none.
const FRAME_CSS =
  "html,body{height:100%;margin:0;background:transparent;overflow:hidden}" +
  ".tile{min-height:100%;box-shadow:none}button{pointer-events:none}";

export async function snapshotOf(
  tile: HTMLElement,
  columns: number,
): Promise<TileSnapshot> {
  const copy = tile.cloneNode(true) as HTMLElement;
  copy.classList.remove(...BOARD_ONLY_CLASSES);
  copy.removeAttribute("draggable");
  for (const part of copy.querySelectorAll(".bar, .pinned")) part.remove();

  const probe = document.createElement("div");
  probe.style.cssText = `position:absolute;visibility:hidden;width:${columns * COLUMN_PX + (columns - 1) * GAP_PX}px`;
  probe.append(copy);
  document.body.append(probe);
  const height = Math.ceil(copy.getBoundingClientRect().height);
  probe.remove();

  // ponytail: the whole page's CSS goes along, about 100 kB a widget; pick the tile's rules if that gets heavy.
  const html =
    `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
    `<style>${await pageCss()}</style><style>${FRAME_CSS}</style></head>` +
    `<body>${copy.outerHTML}</body></html>`;
  return { html, height, columns };
}

async function pageCss(): Promise<string> {
  const rules = [...document.styleSheets].flatMap((sheet) => [
    ...sheet.cssRules,
  ]);
  const parts = await Promise.all(
    rules.map((rule) =>
      rule instanceof CSSFontFaceRule ? fontFace(rule) : rule.cssText,
    ),
  );
  return parts.join("\n");
}

/** The Latin face with its file inside the rule, because the widget's frame cannot load our files. */
async function fontFace(rule: CSSFontFaceRule): Promise<string> {
  // Browsers write the range of the Latin file as U+0000-00FF or as U+0-FF.
  const isLatin = /unicode-range:\s*U\+0+-0*FF\b/i.test(rule.cssText);
  const path = /url\(["']?([^"')]+)/.exec(
    rule.style.getPropertyValue("src"),
  )?.[1];
  if (!isLatin || path === undefined) return "";
  const address = new URL(path, rule.parentStyleSheet?.href ?? location.href);
  const file = await (await fetch(address)).blob();
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
  return rule.cssText.replace(/url\([^)]*\)/, `url("${data}")`);
}
