// jsdom has no canvas: give Paper.js a no-op 2D context so the scene graph and
// geometry (what the editor tests exercise) work without rendering.
const noop = () => undefined;
const context = new Proxy(
  {},
  {
    get: (_target, prop) => {
      if (prop === "measureText") return () => ({ width: 0 });
      if (prop === "getImageData") return () => ({ data: new Uint8ClampedArray(4) });
      if (prop === "createLinearGradient" || prop === "createRadialGradient") return () => ({ addColorStop: noop });
      return noop;
    },
    set: () => true,
  },
);

HTMLCanvasElement.prototype.getContext = function () {
  return context as unknown as CanvasRenderingContext2D;
} as unknown as HTMLCanvasElement["getContext"];
