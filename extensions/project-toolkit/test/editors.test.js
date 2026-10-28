"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { harness } = require("./editor-harness");

const edit = (version, value, id = 1) => ({ type: "edit", id, version, operations: [{ op: "set", path: ["project", "name"], value }] });

test("custom editor applies minimal document edits and follows undo, save and raw changes", async () => {
  const h = harness("# comment\nproject:\n  name: old\n");
  const p = await h.resolve();
  await p.receive({ type: "ready" });
  assert.ok(p.messages.at(-1).schema.$defs.JobSpec);
  assert.equal(p.messages.at(-1).value.project.name, "old");
  await p.receive(edit(1, "new"));
  assert.equal(h.document.getText(), "# comment\nproject:\n  name: new\n");
  assert.equal(h.edits[0].text, "new");
  assert.equal(p.messages.at(-1).ack, 1);
  assert.equal(p.messages.at(-1).dirty, true);
  h.external("# comment\nproject:\n  name: old\n"); // VS Code undo/redo or a raw edit.
  assert.equal(p.messages.at(-1).value.project.name, "old");
  await p.receive({ type: "save" });
  assert.equal(p.messages.at(-1).dirty, false);
  await p.receive({ type: "raw" });
  assert.deepEqual(h.executed.at(-1), ["vscode.openWith", h.document.uri, "default"]);
  await p.receive({ type: "validate" });
  assert.equal(h.validationCount(), 1);
  p.dispose();
  h.external("jobs: {}\n");
  assert.equal(p.messages.at(-1).value.project.name, "old");
});

test("external changes, failed edits and lost trust cannot silently overwrite YAML", async () => {
  const h = harness("project: {name: old}\n");
  const p = await h.resolve();
  h.external("project: {name: external}\n");
  await p.receive(edit(1, "stale"));
  assert.match(p.messages.at(-1).issue, /changed outside/);
  assert.ok(h.document.getText().includes("external"));
  h.setAccepted(false);
  await p.receive(edit(2, "rejected"));
  assert.match(p.messages.at(-1).issue, /could not apply/);
  assert.ok(h.document.getText().includes("external"));
  h.api.workspace.isTrusted = false;
  await p.receive(edit(2, "untrusted"));
  assert.match(p.messages.at(-1).issue, /Trust this workspace/);
  assert.ok(h.document.getText().includes("external"));
});

test("invalid YAML retains Raw YAML access and failed saves do not validate", async () => {
  const h = harness("jobs: [\n");
  const p = await h.resolve();
  await p.receive({ type: "ready" });
  assert.ok(p.messages.at(-1).error);
  await p.receive({ type: "raw" });
  assert.equal(h.executed[0][0], "vscode.openWith");
  h.setSaved(false);
  await p.receive({ type: "validate" });
  assert.equal(h.validationCount(), 0);
  assert.match(p.messages.at(-1).issue, /could not be saved/);
});


test("opening a tree field navigates an existing form and never creates an arbitrary replacement file", async () => {
  const h = harness();
  await h.editors.open(h.document.uri, ["jobs"]);
  assert.equal(h.executed[0][2], "project-toolkit.configuration");
  const p = await h.resolve();
  await p.receive({ type: "ready" });
  assert.deepEqual(p.messages.at(-1).selection, ["jobs"]);
  await h.editors.open(h.document.uri, ["jobs", "build"]);
  assert.equal(p.revealed, true);
  assert.deepEqual(p.messages.at(-1).selection, ["jobs", "build"]);
});

test("parameter window validates values, filters secrets, and resolves only once", async () => {
  const h = harness();
  const target = { name: "build", spec: { params: [{ name: "count", type: "int", required: true }, { name: "password", type: "secret" }] } };
  const result = h.editors.parameters(target, { preview: false });
  const p = h.panels[0];
  await p.receive({ type: "ready" });
  assert.equal(p.messages.at(-1).params.length, 1);
  await p.receive({ type: "submit", params: { count: "no" }, preview: false });
  assert.equal(p.isDisposed, false);
  assert.match(p.messages.at(-1).issue, /whole number/);
  await p.receive({ type: "submit", params: { count: "2" }, preview: true });
  assert.deepEqual(await result, { params: { count: "2" }, preview: true });
  assert.equal(p.isDisposed, true);
  const cancelled = h.editors.parameters(target, { preview: false });
  h.panels[1].dispose();
  assert.equal(await cancelled, undefined);
});
