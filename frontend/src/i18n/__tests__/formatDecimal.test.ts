import { describe, expect, it } from "vitest";

import { formatDecimal } from "..";

describe("formatDecimal", () => {
  it("uses a decimal comma in French so 1.939 sheets is not read as 1939", () => {
    expect(formatDecimal(1.939, "fr")).toBe("1,94");
  });

  it("uses a decimal point in English", () => {
    expect(formatDecimal(1.939, "en")).toBe("1.94");
  });

  it("drops trailing zeros and honours the digit count", () => {
    expect(formatDecimal(3, "fr")).toBe("3");
    expect(formatDecimal(0.0004, "en", 3)).toBe("0");
    expect(formatDecimal(12.3456, "en", 3)).toBe("12.346");
  });
});
