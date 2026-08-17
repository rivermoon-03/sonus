import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const imageUrl = new URL("./assets/wh-1000xm6-black.svg", import.meta.url);
const imagePath = fileURLToPath(imageUrl);

test("headset asset is a native SVG illustration", () => {
  assert.ok(existsSync(imagePath), "WH-1000XM6 illustration must be present");
  const image = readFileSync(imagePath, "utf8");
  assert.match(image, /<svg[^>]+viewBox="0 0 600 600"/);
  assert.match(image, /<linearGradient/);
  assert.doesNotMatch(image, /<image\b/);
});
