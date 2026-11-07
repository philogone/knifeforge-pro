import { describe, expect, it } from "vitest";

import { en } from "@/i18n/en";
import { fr } from "@/i18n/fr";

describe("dictionaries", () => {
  it("French and English carry the same keys", () => {
    const missingInEn = Object.keys(fr).filter((k) => !(k in en));
    const missingInFr = Object.keys(en).filter((k) => !(k in fr));
    expect({ missingInEn, missingInFr }).toEqual({ missingInEn: [], missingInFr: [] });
  });

  it("French puts a non-breaking space before a colon", () => {
    const bad = Object.entries(fr).filter(([, v]) => /[^\s ]:(\s|$)/.test(v) && !/https?:/.test(v));
    expect(bad).toEqual([]);
  });
});
