import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, formatApiDetail } from "../useApi";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("formatApiDetail", () => {
  it("keeps plain string details", () => {
    expect(formatApiDetail("Invalid credentials")).toBe("Invalid credentials");
  });

  it("turns a FastAPI 422 list into readable text instead of [object Object]", () => {
    const detail = [
      { type: "value_error", loc: ["body", "email"], msg: "value is not a valid email address" },
      { type: "missing", loc: ["body", "password"], msg: "Field required" },
    ];
    const text = formatApiDetail(detail);
    expect(text).toBe("email: value is not a valid email address; password: Field required");
    expect(text).not.toContain("[object Object]");
  });

  it("uses the message of structured details", () => {
    expect(formatApiDetail({ message: "Insufficient stock", feasibility: {} })).toBe("Insufficient stock");
  });

  it("ApiError.message is the readable text", () => {
    expect(new ApiError(422, [{ loc: ["body", "x"], msg: "bad" }]).message).toBe("x: bad");
  });
});

describe("apiFetch 401 handling", () => {
  it("surfaces bad credentials on the login call without redirecting", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(401, { detail: "Invalid credentials" })));
    localStorage.setItem("knifeforge_token", "keep-me");
    const before = window.location.href;
    await expect(apiFetch("/auth/login", { method: "POST", body: "{}" })).rejects.toMatchObject({
      status: 401,
      message: "Invalid credentials",
    });
    expect(window.location.href).toBe(before);
    expect(localStorage.getItem("knifeforge_token")).toBe("keep-me");
  });

  it("still clears the session on a 401 from any other endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(401, { detail: "Not authenticated" })));
    localStorage.setItem("knifeforge_token", "expired");
    await expect(apiFetch("/admin/materials")).rejects.toBeInstanceOf(ApiError);
    expect(localStorage.getItem("knifeforge_token")).toBeNull();
  });
});
