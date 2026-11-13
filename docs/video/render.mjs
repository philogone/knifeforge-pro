// Render motion.html to an MP4, frame by frame (deterministic, no dropped frames).
//
//   node render.mjs [out.mp4] [fps]            (needs playwright-core, Edge or Chrome, ffmpeg)
//   node render.mjs --frames 2,9,16 shots/     (a few stills, to check the layout)
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const browser = await chromium.launch({ channel: process.env.KF_BROWSER || "msedge" });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(resolve(here, "motion.html")).href + "?render=1");
await page.evaluate(() => window.ready);
const duration = await page.evaluate(() => window.DURATION);

if (args[0] === "--frames") {
  const dir = resolve(args[2] || "shots");
  mkdirSync(dir, { recursive: true });
  for (const t of args[1].split(",").map(Number)) {
    await page.evaluate((x) => window.render(x), t);
    writeFileSync(resolve(dir, `t${String(t).padStart(5, "0")}.png`), await page.screenshot());
  }
} else {
  const out = resolve(args[0] || resolve(here, "knifeforge-pro.mp4"));
  const fps = Number(args[1] || 30);
  const ffmpeg = spawn(process.env.FFMPEG || "ffmpeg", [
    "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const frames = Math.round(duration * fps);
  for (let i = 0; i < frames; i++) {
    await page.evaluate((x) => window.render(x), i / fps);
    const png = await page.screenshot({ type: "png" });
    if (!ffmpeg.stdin.write(png)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    if (i % (fps * 5) === 0) console.log(`${(i / fps).toFixed(0)} s / ${duration} s`);
  }
  ffmpeg.stdin.end();
  await new Promise((r) => ffmpeg.on("close", r));
  console.log("written", out);
}
await browser.close();
