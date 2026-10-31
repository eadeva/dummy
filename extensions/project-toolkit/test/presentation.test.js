"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const P = require("../media/presentation");

test("GUI identity follows logical and document-bound forms including unsaved edits", () => {
  const value = { jobs: { viewer: {gui: true} } };
  assert.equal(P.entity(["jobs", "viewer"], {logical: true, value}), "gui");
  assert.equal(P.entity(["jobs"], {logical: true, value}), "job");
  assert.equal(P.entity(["jobs", "viewer", "gui"], {logical: true, value}), undefined);
  const state = {value: {gui: true}, pathBindings: [{document_path: [], path: ["jobs", "viewer"]}]};
  assert.equal(P.entity([], state), "gui");
  state.value.gui = false;
  assert.equal(P.entity([], state), "job");
  assert.equal(P.icon(value.jobs.viewer, ["jobs", "viewer"]), "window");
});
