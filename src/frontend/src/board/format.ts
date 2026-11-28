// Figures and dates as the boards print them: 1'092.35, 15'646, 23.12., November.

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function withApostrophes(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, "'");
}

/** 1092.35 → "1'092.35", always with two decimals. */
export function money(amount: number): string {
  const [whole, cents] = Math.abs(amount).toFixed(2).split(".");
  const sign = amount < 0 && Number(cents) + Number(whole) > 0 ? "-" : "";
  return `${sign}${withApostrophes(whole)}.${cents}`;
}

/** 15645.8 → "15'646", for the labels of bars. */
export function moneyRounded(amount: number): string {
  const rounded = Math.round(Math.abs(amount));
  return `${amount < 0 && rounded > 0 ? "-" : ""}${withApostrophes(String(rounded))}`;
}

/** "2026-12-23" → "23.12." */
export function day(date: string): string {
  const [, month, dayOfMonth] = date.split("-");
  return `${dayOfMonth}.${month}.`;
}

/** "2026-12-23" → "23.12.2026" */
export function fullDate(date: string): string {
  const [year, month, dayOfMonth] = date.split("-");
  return `${dayOfMonth}.${month}.${year}`;
}

/** "2026-11" → "November" */
export function monthName(month: string): string {
  return MONTHS[Number(month.split("-")[1]) - 1] ?? month;
}

/** "2026-11" → "Nov" */
export function monthShort(month: string): string {
  return monthName(month).slice(0, 3);
}

/** 93.164 → "93.16 %" */
export function percent(value: number): string {
  return `${Number(value.toFixed(2))} %`;
}

/** Days from one ISO date to another. */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000);
}

/** The ISO date a number of days after another. */
export function addDays(date: string, days: number): string {
  return new Date(Date.parse(date) + days * 86_400_000)
    .toISOString()
    .slice(0, 10);
}
