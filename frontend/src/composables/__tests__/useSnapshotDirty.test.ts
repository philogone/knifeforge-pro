import { describe, expect, it } from "vitest";
import { nextTick, reactive } from "vue";

import { useSnapshotDirty } from "../useSnapshotDirty";

describe("useSnapshotDirty", () => {
  it("is clean right after loading values and marking clean, even after Vue flushes", async () => {
    const form = reactive({ name: "", material_id: 0 });
    const { dirty, markClean } = useSnapshotDirty(() => ({ ...form }));
    expect(dirty.value).toBe(false); // nothing loaded yet

    form.name = "Bushcraft — profil de lame";
    form.material_id = 3;
    markClean();
    await nextTick();
    expect(dirty.value).toBe(false);
  });

  it("detects an edit and clears when the edit is reverted", () => {
    const form = reactive({ name: "Lame" });
    const { dirty, markClean } = useSnapshotDirty(() => ({ ...form }));
    markClean();
    form.name = "Lame 2";
    expect(dirty.value).toBe(true);
    form.name = "Lame";
    expect(dirty.value).toBe(false);
  });

  it("is clean again after a save", () => {
    const form = reactive({ name: "A" });
    const { dirty, markClean } = useSnapshotDirty(() => ({ ...form }));
    markClean();
    form.name = "B";
    markClean();
    expect(dirty.value).toBe(false);
  });
});
