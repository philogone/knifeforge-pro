import { describe, expect, it } from "vitest";
import { ref } from "vue";

import { byText, matches, normalize, useListSearch } from "@/composables/useListSearch";

describe("list search", () => {
  it("ignores case and accents", () => {
    expect(normalize("  Acier TREMPÉ ")).toBe("acier trempe");
    expect(matches(["Acier trempé", null], "trempe acier")).toBe(true);
    expect(matches(["Noyer"], "noyer chêne")).toBe(false);
    expect(matches(["anything"], "   ")).toBe(true);
  });

  it("sorts in French alphabetical order", () => {
    expect(["Zèbre", "écorce", "Acier"].sort(byText)).toEqual(["Acier", "écorce", "Zèbre"]);
  });

  it("filters then sorts, and follows the source list", () => {
    const items = ref([{ name: "Lame B" }, { name: "Garde" }, { name: "Lame A" }]);
    const list = useListSearch(items, (i) => [i.name], [{ key: "name", label: "", compare: (a, b) => byText(a.name, b.name) }]);
    list.query.value = "lame";
    expect(list.visible.value.map((i) => i.name)).toEqual(["Lame A", "Lame B"]);
    items.value.push({ name: "Lame 0" });
    expect(list.visible.value.map((i) => i.name)).toEqual(["Lame 0", "Lame A", "Lame B"]);
    expect(list.total.value).toBe(4);
  });
});
