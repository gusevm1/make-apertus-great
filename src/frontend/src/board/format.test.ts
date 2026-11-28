import { describe, expect, it } from "vitest";
import { day, money, moneyRounded } from "./format";

describe("money", () => {
  it("prints francs as the boards do", () => {
    expect(money(1092.35)).toBe("1'092.35");
    expect(money(131212.64)).toBe("131'212.64");
    expect(money(58)).toBe("58.00");
    expect(money(-600)).toBe("-600.00");
    expect(money(0.004)).toBe("0.00");
  });

  it("rounds the labels of bars to whole francs", () => {
    expect(moneyRounded(17273.6)).toBe("17'274");
    expect(moneyRounded(9191.2)).toBe("9'191");
  });
});

describe("day", () => {
  it("prints a date as day and month", () => {
    expect(day("2026-12-23")).toBe("23.12.");
  });
});
