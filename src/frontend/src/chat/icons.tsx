const BASE = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

export function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" {...BASE} strokeWidth="1.8">
      <path d="M2.5 7.5 5.5 10.5 11.5 4" />
    </svg>
  );
}

export function BookmarkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" {...BASE} strokeWidth="1.5">
      <path d="M3.5 1.8h7v10.4L7 9.8l-3.5 2.4Z" />
    </svg>
  );
}

export function PaperclipIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" {...BASE} strokeWidth="1.5">
      <path d="M14.5 8.5 9 14a3.5 3.5 0 0 1-5-5l6-6a2.3 2.3 0 0 1 3.3 3.3l-6 6a1.2 1.2 0 0 1-1.7-1.7L11 5.3" />
    </svg>
  );
}

export function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" {...BASE} strokeWidth="1.5">
      <rect x="6.5" y="2" width="5" height="9" rx="2.5" />
      <path d="M3.5 9a5.5 5.5 0 0 0 11 0M9 14.5V16" />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" {...BASE} strokeWidth="1.8">
      <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
    </svg>
  );
}

export function CloseIcon({ size = 10 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" {...BASE} strokeWidth="1.6">
      <path d="M2 2l6 6M8 2l-6 6" />
    </svg>
  );
}
