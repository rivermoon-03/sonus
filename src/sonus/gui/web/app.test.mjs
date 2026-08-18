import test from "node:test";
import assert from "node:assert/strict";

import {
  createState,
  pushHistory,
  reduceState,
  sparklinePoints,
  supportLabel,
  valueLabel,
} from "./app.js";

test("initial application state requires disclaimer before writes", () => {
  const state = createState();
  assert.equal(state.theme, "light");
  assert.equal(state.readOnly, false);
  assert.equal(state.disclaimerAccepted, false);
  assert.equal(state.connection.state, "idle");
});

test("feature updates preserve verified writable metadata", () => {
  const state = reduceState(createState(), {
    type: "feature",
    payload: { key: "dsee", value: true, writable: true },
  });
  assert.equal(state.features.dsee.value, true);
  assert.equal(state.features.dsee.writable, true);
});

test("friendly labels handle booleans, missing data, and nested values", () => {
  assert.equal(valueLabel(true), "켜짐");
  assert.equal(valueLabel(null), "확인 중");
  assert.equal(valueLabel({ level: 67 }), "67%");
  assert.equal(valueLabel("not_worn"), "미착용");
});

test("debug history ignores repeated identical samples from unrelated re-renders", () => {
  // A single debug poll dispatches ~10 feature updates; renderDebug() re-reads the
  // same unchanged battery/ambient value on each one. Regression test for a bug
  // where that collapsed a ~120s rolling window down to ~12s of real samples.
  const history = [];
  pushHistory(history, 82);
  pushHistory(history, 82);
  pushHistory(history, 82);
  assert.deepEqual(history, [82]);

  pushHistory(history, 81);
  assert.deepEqual(history, [82, 81]);
});

test("debug history caps at 40 samples", () => {
  const history = [];
  for (let level = 0; level < 45; level++) pushHistory(history, level);
  assert.equal(history.length, 40);
  assert.equal(history[history.length - 1], 44);
});

test("support labels reflect capability, not an on/off setting", () => {
  assert.equal(supportLabel(true), "지원됨");
  assert.equal(supportLabel(false), "미지원");
  assert.equal(supportLabel(null), "확인 중");
});

test("sparkline points need at least two samples and scale against the given max", () => {
  assert.equal(sparklinePoints([50], 100), "");
  const points = sparklinePoints([0, 100], 100);
  assert.equal(points, "0.0,60.0 200.0,0.0");
});
