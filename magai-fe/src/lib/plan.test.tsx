import { describe, expect, it } from "vitest";

import { formatPrice, formatUsage } from "./plan";

describe("formatUsage", () => {
  it("reads as used-of-allowed when there is an allowance", () => {
    expect(formatUsage(2, 3)).toBe("2 of 3");
  });

  it("takes a separator so a meter can render a slash", () => {
    expect(formatUsage(2, 3, "/")).toBe("2 / 3");
  });

  it("drops the denominator when the plan has no allowance", () => {
    // A tool bought outright sits on the free plan, whose live-tool cap is
    // zero. "1 of 0" is arithmetic, not information — and it shipped twice
    // before this function existed.
    expect(formatUsage(1, 0)).toBe("1");
    expect(formatUsage(0, 0)).toBe("0");
  });

  it("groups large numbers", () => {
    expect(formatUsage(1248, 10000)).toContain("1,248");
  });
});

describe("formatPrice", () => {
  it("renders whole dollars from integer cents", () => {
    expect(formatPrice(9900)).toBe("$99");
    expect(formatPrice(19900)).toBe("$199");
  });

  it("shows free as $0 rather than a currency-formatted zero", () => {
    expect(formatPrice(0)).toBe("$0");
  });
});
