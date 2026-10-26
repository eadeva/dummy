"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const core = require("../src/core");
const { inventory } = require("./fixtures");

function target(kind = "job") {
  const project = inventory().projects[0];
  return { kind, project, name: "build", spec: project.jobs[0] };
}

test("inventory accepts the versioned CLI contract and isolated broken members", () => {
  const doc = inventory();
  doc.projects.push({ alias: "broken", root: doc.root, entry_file: path.join(doc.root, "bad.yml"), error: "Invalid configuration" });
  assert.deepEqual(core.parseInventory(JSON.stringify(doc)), doc);
});

test("malformed inventories produce actionable errors", () => {
  for (const value of [null, {}, { schema_version: 2 }, { ...inventory(), root: "relative" }, { ...inventory(), projects: [null] }]) {
    assert.throws(() => core.parseInventory(JSON.stringify(value)), /inventory|repository paths/);
  }
  const bad = inventory();
  bad.projects[0].jobs[0].params[0].type = "secret";
  assert.throws(() => core.parseInventory(JSON.stringify(bad)), /Incomplete/);
  assert.throws(() => core.parseInventory("old PTK output"), /Update PTK/);
});

test("all public parameter types, including lists, are accepted", () => {
  const doc = inventory();
  doc.projects[0].jobs[0].params = ["str", "int", "float", "bool", "path", "choice", "list"].map(type => ({ name: type, type, required: false, choices: [] }));
  assert.doesNotThrow(() => core.parseInventory(JSON.stringify(doc)));
});

test("selected variants fall back after removal and never select an abstract variant", () => {
  const project = inventory().projects[0];
  assert.equal(core.selectedVariant(project, "large"), "large");
  assert.equal(core.selectedVariant(project, "removed"), "small");
  assert.equal(core.selectedVariant(project, "base"), "small");
  project.default_variant = "removed";
  assert.equal(core.selectedVariant(project), undefined);
});

test("job arguments put global options first and preserve literal metacharacters", () => {
  const t = target();
  const literal = "folder with spaces/$(touch unwanted);'value";
  assert.deepEqual(core.argsFor(t, { variant: "large", params: { output_path: literal } }), [
    "--config", t.project.entry_file, "--variant", "large", "run", "build", "--param", `output_path=${literal}`,
  ]);
});

test("previews translate typed options and boolean flags", () => {
  assert.deepEqual(core.argsFor(target(), { preview: true, params: { output_path: "some folder", verbose: "false" } }).slice(2),
    ["dry-run", "build", "--output-path", "some folder", "--no-verbose"]);
  assert.equal(core.argsFor(target(), { preview: true, params: { verbose: "true" } }).at(-1), "--verbose");
  assert.throws(() => core.argsFor(target(), { preview: true, params: { verbose: "invalid" } }), /Boolean/);
  assert.throws(() => core.argsFor(target(), { preview: "true" }), /boolean/);
  assert.throws(() => core.argsFor(target(), { params: { token: "secret" } }), /unknown or secret/);
});

test("workflows retain their authored variants and resolve shared names explicitly", () => {
  assert.deepEqual(core.argsFor(target("workflow"), { variant: "large" }).slice(2), ["workflow", "run", "build"]);
  assert.deepEqual(core.argsFor({ kind: "workflow", name: "all" }, { preview: true }), ["workflow", "dry-run", "all"]);
  assert.deepEqual(core.argsFor(target("report"), { variant: "large" }).slice(2), ["--variant", "large", "report", "open", "build"]);
  assert.deepEqual(core.argsFor(target("variant")).slice(2), ["variant", "show", "build"]);
  assert.deepEqual(core.argsFor(target("validate")).slice(2), ["setup", "config", "validate"]);
});

test("target discovery preserves healthy VMR members and workspace workflows", () => {
  const doc = inventory();
  doc.projects.push({ error: "bad project" });
  doc.workflows.push({ name: "all" });
  const targets = core.availableTargets([{ inventory: doc, folder: "workspace" }, { error: "unavailable" }]);
  assert.deepEqual(targets.map(t => [t.kind, t.name]), [["job", "build"], ["workflow", "build"], ["workflow", "all"]]);
  assert.equal(targets[2].project, undefined);
});

test("discovery invokes an actual executable and parses stdout without a shell", async () => {
  const doc = inventory(process.cwd());
  const script = `if (process.argv.slice(1).join(' ') !== 'describe --json') process.exit(3); process.stdout.write(${JSON.stringify(JSON.stringify(doc))})`;
  assert.deepEqual(await core.readInventory({ executable: process.execPath, arguments: ["-e", script, "--"], timeout: 10 }, process.cwd()), doc);
});

test("missing executables, failing processes and timeouts are reported", async () => {
  await assert.rejects(core.readInventory({ executable: path.resolve("nonexistent-ptk-executable"), arguments: [], timeout: 1 }, process.cwd()), /executable not found/);
  await assert.rejects(core.readInventory({ executable: process.execPath, arguments: ["-e", "process.stderr.write('invalid project'); process.exit(2)", "--"], timeout: 10 }, process.cwd()), /invalid project/);
  await assert.rejects(core.readInventory({ executable: process.execPath, arguments: ["-e", "setTimeout(() => {}, 5000)", "--"], timeout: 0.1 }, process.cwd()), /timed out/);
});
