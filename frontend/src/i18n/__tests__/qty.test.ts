import { describe, expect, it } from "vitest";

import { useI18n } from "@/i18n";

describe("qty", () => {
  const { qty, setLocale } = useI18n();

  it("prints the area unit the API sends as mm^2 with a superscript", () => {
    setLocale("fr");
    expect(qty(87250, "mm^2").replace(/\s/g, " ")).toBe("87 250 mm²");
  });

  it("names counted units in the reader's language", () => {
    setLocale("fr");
    expect(qty(1, "unit")).toBe("1 unité");
    expect(qty(20, "unit")).toBe("20 unités");
  });
});
