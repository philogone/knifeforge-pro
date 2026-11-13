import { afterEach, describe, expect, it } from "vitest";

import { setLocale, setTrade, useI18n } from "@/i18n";

describe("trade vocabulary", () => {
  afterEach(() => setTrade("knifemaker"));

  it("uses the blacksmith's words where they differ, the shared ones elsewhere", () => {
    setLocale("fr");
    const { t } = useI18n();
    expect(t("knifeModels.title")).toBe("Modèles de couteaux");
    setTrade("blacksmith");
    expect(t("knifeModels.title")).toBe("Modèles d'ouvrages");
    expect(t("orders.stage.install")).toBe("Pose");
    expect(t("nav.orders")).toBe(t("nav.orders")); // no overlay: unchanged
    setLocale("en");
    expect(t("knifeModels.title")).toBe("Piece models");
  });
});
