import test from "node:test";
import assert from "node:assert/strict";

import { createState, reduceState, valueLabel } from "./app.js";

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
