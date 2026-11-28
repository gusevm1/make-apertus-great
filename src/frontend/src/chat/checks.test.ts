import { describe, expect, it } from "vitest";
import { checkFailure, checkLabel, decides } from "./checks";

describe("check words", () => {
  it("says in plain words what a failed check means", () => {
    expect(checkFailure("figures_in_context")).toBe(
      "an amount may belong to another month or total",
    );
    expect(checkLabel("figures_found")).toBe("Amounts in your data");
  });

  it("never shows an unknown check id", () => {
    expect(checkFailure("brand_new_check")).toBe("a check did not pass");
    expect(checkLabel("brand_new_check")).toBe("Check");
  });

  it("leaves the corrected draft out of what passed or failed", () => {
    expect(decides("figures_found_draft")).toBe(false);
    expect(decides("figures_found")).toBe(true);
  });
});
