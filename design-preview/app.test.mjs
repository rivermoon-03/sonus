import assert from "node:assert/strict";
import test from "node:test";

import { applyTheme, resolveInitialTheme, toggleTheme } from "./app.js";

test("defaults to light unless dark was explicitly stored", () => {
  assert.equal(resolveInitialTheme(null), "light");
  assert.equal(resolveInitialTheme("light"), "light");
  assert.equal(resolveInitialTheme("dark"), "dark");
  assert.equal(resolveInitialTheme("unexpected"), "light");
});

test("applies the selected theme to the page and accessible toggle", () => {
  const root = { dataset: {} };
  const attributes = new Map();
  const toggle = {
    setAttribute(name, value) {
      attributes.set(name, value);
    },
  };

  applyTheme(root, toggle, "dark");

  assert.equal(root.dataset.theme, "dark");
  assert.equal(attributes.get("aria-pressed"), "true");
  assert.equal(attributes.get("aria-label"), "라이트 테마로 전환");
});

test("toggles and persists the next explicit theme", () => {
  const stored = new Map();
  const storage = {
    setItem(key, value) {
      stored.set(key, value);
    },
  };

  assert.equal(toggleTheme("light", storage), "dark");
  assert.equal(stored.get("sonus-theme"), "dark");
  assert.equal(toggleTheme("dark", storage), "light");
  assert.equal(stored.get("sonus-theme"), "light");
});
