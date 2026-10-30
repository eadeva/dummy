"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const D = require("../media/dependencies"), model = require("../src/config-model");
const { harness } = require("./editor-harness");
const graph = { check: { run: "check" }, test: { run: "test", needs: ["check"] }, package: { run: "package", needs: ["test"] }, docs: { run: "docs" } };

test("workflow choices exclude used repository jobs, including qualified local aliases", () => {
  const configuration = { repository: { alias: "app" }, jobs: { check: {}, test: {}, package: {} } };
  const calls = { one: { job: "app:check" }, two: { job: "other:test" }, three: { job: "package" } };
  assert.deepEqual(D.availableJobs(configuration, calls), ["test"]);
  assert.deepEqual(D.availableJobs(configuration, calls, "one"), ["check", "test"]);
  assert.throws(() => D.validateTargets({ ...calls, four: { job: "check" } }, "app"), /only be chosen once/);
  assert.doesNotThrow(() => D.validateTargets({ ...calls, four: { job: "test" } }, "app"));
});

test("dependency edits preserve joins, reject backwards connections and repair imported bad edges", () => {
  assert.deepEqual(D.update(graph, "docs", "package"), ["test", "docs"]);
  assert.throws(() => D.update(graph, "package", "check"), /cycle/);
  assert.throws(() => D.update(graph, "check", "check"), /itself/);
  assert.throws(() => D.update(graph, "test", "package"), /already exists/);
  assert.throws(() => D.update(graph, "missing", "test"), /no longer exists/);
  assert.deepEqual(D.update({ a: { needs: ["missing"] } }, "missing", "a", true), []);
  const chain = Object.fromEntries(Array.from({ length: 2000 }, (_, i) => [`n${i}`, { needs: i ? [`n${i - 1}`] : [] }]));
  assert.throws(() => D.update(chain, "n1999", "n0"), /cycle/);
});

test("edge writes retain authored order, comments and unrelated values and protect YAML aliases", () => {
  const before = "steps:\n  check: {run: check}\n  test:\n    run: test # keep command\n    needs: # keep list\n      - check # keep prerequisite\n  docs: {run: docs}\n";
  const operation = { op: "dependency", path: ["steps", "test"], prerequisite: "docs", remove: false };
  const after = model.edit(before, [operation]);
  assert.deepEqual(model.inspect(after).value.steps.test.needs, ["check", "docs"]);
  for (const comment of ["# keep command", "# keep list", "# keep prerequisite"]) assert.ok(after.includes(comment));
  assert.deepEqual(Object.keys(model.inspect(after).value.steps), ["check", "test", "docs"]);
  const removed = model.edit(after, [{ ...operation, prerequisite: "check", remove: true }]);
  assert.deepEqual(model.inspect(removed).value.steps.test.needs, ["docs"]);
  assert.match(removed, /# keep command/);
  const scalar = model.edit("steps:\n  check: {run: check}\n  docs: {run: docs}\n  test:\n    run: test\n    needs: check # retain scalar comment\n", [operation]);
  assert.deepEqual(model.inspect(scalar).value.steps.test.needs, ["check", "docs"]);
  assert.match(scalar, /# retain scalar comment/);
  assert.throws(() => model.edit("steps:\n  check: {run: check}\n  test: {run: test, needs: &deps [check]}\n  docs: {run: docs, needs: *deps}\n", [{ ...operation, path: ["steps", "docs"] }]), /complex YAML/);
});

test("host rejects stale and cyclic graph edits before applying a workspace edit", async () => {
  const h = harness("steps:\n  check: {run: check}\n  test: {run: test, needs: [check]}\n");
  const panel = await h.resolve();
  const message = { type: "edit", id: 1, version: 1, operations: [{ op: "dependency", path: ["steps", "check"], prerequisite: "test", remove: false }] };
  await panel.receive(message);
  assert.match(panel.messages.at(-1).issue, /cycle/); assert.equal(h.edits.length, 0);
  h.external(h.document.getText() + "# another editor changed this\n");
  await panel.receive({ ...message, operations: [{ ...message.operations[0], path: ["steps", "test"], prerequisite: "check", remove: true }] });
  assert.match(panel.messages.at(-1).issue, /changed outside/); assert.equal(h.edits.length, 0);
});
