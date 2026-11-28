/** What each server check looks at, and what it means for the customer when it fails. */
const CHECKS: Record<string, { label: string; failed: string }> = {
  figures_found: {
    label: "Amounts in your data",
    failed: "an amount in this answer is not in your bookings",
  },
  figures_found_draft: {
    label: "Amounts in the first draft",
    failed: "the first draft had an amount that is not in your bookings",
  },
  figures_in_context: {
    label: "Amounts in the right period",
    failed: "an amount may belong to another month or total",
  },
  dates_match: {
    label: "Dates in your data",
    failed: "a date in this answer is not in your data",
  },
  answer_complete: {
    label: "Complete answer",
    failed: "an amount in this answer could not be worked out",
  },
  tool_calls_valid: {
    label: "Every step got its figures",
    failed: "a step could not get its figures",
  },
  guardrail: {
    label: "Topic check",
    failed: "the topic check flagged this question",
  },
};

export function checkLabel(name: string): string {
  return CHECKS[name]?.label ?? "Check";
}

export function checkFailure(name: string): string {
  return CHECKS[name]?.failed ?? "a check did not pass";
}

/** False for the draft check, which only records that the first draft was corrected. */
export function decides(name: string): boolean {
  return name !== "figures_found_draft";
}
