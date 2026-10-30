"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const V = require("../media/variables"), S = require("../media/schema");
const schema = require("../media/config-schema.json"), variables = require("./variable-fixtures");
const { bindingsForFile, schemaForFile } = require("../src/project-edits");

test("installed field capabilities filter literal fields, defaults, jobs, named steps and credentials", () => {
  const value = { project: { name: "literal" }, vars: { nested: { text: "" } }, jobs: { build: {
    params: { mode: { default: "" } }, env: { MODE: "" }, steps: {child: {run: ["echo", ""], with: {message: ""}, env: {TOKEN: ""}}, short: {run: "echo"}},
  } }, artifactory: { events: { push: { path: "" } } } };
  const names = path => V.available({ logical: true, value, variables }, schema, path, S).map(entry => entry.reference);
  assert.deepEqual(names(["project", "name"]), []);
  assert.ok(names(["vars", "nested", "text"]).includes("git.short_commit"));
  assert.ok(!names(["jobs", "build", "params", "mode", "default"]).includes("run.bin_dir"));
  assert.ok(!names(["jobs", "build", "params", "mode", "default"]).includes("params.mode"));
  const child = ["jobs", "build", "steps", "child"];
  assert.ok(names([...child, "run", 1]).includes("params.mode"));
  assert.ok(!names([...child, "run", 1]).includes("params.other"));
  assert.ok(!names([...child, "run", 1]).includes("secret:service.token"));
  assert.ok(names([...child, "env", "TOKEN"]).includes("secret:service.token"));
  assert.deepEqual(names([...child, "uses"]), []);
  assert.ok(names(["jobs", "build", "steps", "short", "run"]).includes("run.bin_dir"));
  assert.ok(names(["artifactory", "events", "push", "path"]).includes("github.ref_name"));
  assert.ok(!names(["artifactory", "events", "push", "path"]).includes("run.bin_dir"));
});

test("raw file parameter filtering follows PTK's logical bindings", () => {
  const file = "/project/config/jobs/build.ptk.yml";
  const snapshot = { schema, bindings: [{ file: "/project/config/jobs/{name}.ptk.yml", path: ["jobs", "*"], document_path: [] }],
    documents: [{ file: "/project/config/jobs/{name}.ptk.yml", schema: { $ref: "#/$defs/JobSpec" } }] };
  const state = { value: { env: { MODE: "" } }, variables, pathBindings: bindingsForFile(snapshot, file) };
  const entries = V.available(state, schemaForFile(snapshot, file), ["env", "MODE"], S);
  assert.ok(entries.some(entry => entry.reference === "params.mode"));
  assert.ok(!entries.some(entry => entry.reference === "params.other"));
});

test("completion replaces only the active template and ignores escaped or closed tokens", () => {
  assert.deepEqual(V.token("out/${git.sh}/suffix", 12), { start: 4, end: 13, query: "git.sh" });
  assert.equal(V.token("$${git.sh", 9), undefined);
  assert.equal(V.token("${git.commit}", 13), undefined);
  assert.equal(V.token("plain", 5), undefined);
  assert.deepEqual(V.filter(variables.entries, "git short").map(e => e.reference), ["git.short_commit"]);
});
