import { describe, expect, it } from "vitest";

import { ApiError } from "@/composables/useApi";
import { errorMessage } from "@/i18n/apiErrors";

const t = (key: string, vars?: Record<string, string | number>) => (vars ? `${key}:${JSON.stringify(vars)}` : key);

describe("errorMessage", () => {
  it("translates a known server message", () => {
    expect(errorMessage(new ApiError(409, "Material is used by one or more knife models"), t)).toBe("apiError.materialInUse");
  });

  it("matches messages built with values on their fixed start", () => {
    expect(errorMessage(new ApiError(400, "Too many parts to nest (900 > 800); select fewer orders"), t)).toBe("apiError.tooManyParts");
  });

  it("says the server is unreachable when fetch itself fails", () => {
    expect(errorMessage(new TypeError("Failed to fetch"), t)).toBe("apiError.network");
  });

  it("never shows a raw 500 body", () => {
    expect(errorMessage(new ApiError(500, "Traceback ..."), t)).toBe("apiError.server");
  });

  it("keeps validation details, framed", () => {
    expect(errorMessage(new ApiError(422, [{ loc: ["body", "name"], msg: "Field required" }]), t)).toBe('apiError.validation:{"detail":"name: Field required"}');
  });

  it("falls back to the given key for anything else", () => {
    expect(errorMessage(new Error("boom"), t, "common.deleteFailed")).toBe("common.deleteFailed");
  });
});
