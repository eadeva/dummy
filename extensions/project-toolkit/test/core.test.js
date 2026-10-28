"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const core = require("../src/core");
const { inventory, builtinParam } = require("./fixtures");

function target(kind = "job") {
  const project = inventory().projects[0];
  return { kind, project, name: "build", spec: project.jobs[0] };
}

test("inventory accepts the versioned CLI contract and isolated broken members", () => {
  const doc = inventory();
  doc.projects.push({ configuration: { ...doc.projects[0].configuration, value: null }, alias: "broken", root: doc.root, entry_file: path.join(doc.root, "bad.yml"), error: "Invalid configuration" });
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

test("workflows select their owner variants and resolve shared names explicitly", () => {
  assert.deepEqual(core.argsFor(target("workflow"), { variant: "large" }).slice(2), ["--variant", "large", "workflow", "run", "build"]);
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

test("built-in command metadata is required and malformed metadata is rejected", () => {
  const doc = inventory();
  delete doc.projects[0].commands;
  assert.throws(() => core.parseInventory(JSON.stringify(doc)), /built-in command inventory/);
  for (const corrupt of [command => { command.path = ["--unexpected"]; }, command => { command.children = null; },
    command => { command.params = [builtinParam("bad", { kind: "option", option: null })]; }]) {
    const bad = inventory();
    corrupt(bad.projects[0].commands[0]);
    assert.throws(() => core.parseInventory(JSON.stringify(bad)), /built-in command inventory/);
  }
});

test("job and workflow help bypasses required parameters", () => {
  const job = target();
  job.spec.params[0].required = true;
  assert.deepEqual(core.argsFor(job, { help: true }).slice(2), ["build", "--help"]);
  assert.deepEqual(core.argsFor(target("workflow"), { help: true }).slice(2), ["workflow", "run", "build", "--help"]);
});

test("built-in options, repeated values and leading-dash positional arguments stay literal", () => {
  const target = { kind: "builtin", spec: { path: ["setup", "config", "show"], runnable: true, params: [
    builtinParam("path"),
    builtinParam("item", { kind: "option", option: "--item", multiple: true }),
    builtinParam("enabled", { kind: "option", option: "--enabled", secondary_option: "--no-enabled", is_flag: true }),
  ] } };
  assert.deepEqual(core.argsFor(target, { variant: "ignored", inputs: { path: ["--literal;$(value)"], item: ["a b", "-c"], enabled: ["false"] } }),
    ["setup", "config", "show", "--item=a b", "--item=-c", "--no-enabled", "--", "--literal;$(value)"]);
  assert.throws(() => core.argsFor(target, { inputs: { unexpected: ["value"] } }), /Invalid built-in/);
  assert.throws(() => core.argsFor(target, { inputs: { path: "value" } }), /Invalid built-in/);
  assert.throws(() => core.argsFor(target, { inputs: { enabled: ["maybe"] } }), /Invalid flag/);
});

test("built-in required and positional arguments are validated while help needs no values", () => {
  const target = { kind: "builtin", spec: { path: ["setup", "creds", "set"], runnable: true, params: [
    builtinParam("name", { required: true }), builtinParam("field"), builtinParam("extra", { nargs: -1 }),
  ] } };
  assert.throws(() => core.argsFor(target), /Required argument: name/);
  assert.throws(() => core.argsFor(target, { inputs: { name: ["a", "b"] } }), /number of values/);
  assert.throws(() => core.argsFor(target, { inputs: { name: ["a"], extra: ["b"] } }), /preceding positional/);
  assert.deepEqual(core.argsFor(target, { inputs: { name: ["a"], field: ["b"], extra: ["c", "d"] } }),
    ["setup", "creds", "set", "--", "a", "b", "c", "d"]);
  assert.deepEqual(core.argsFor(target, { help: true }), ["setup", "creds", "set", "--help"]);
  assert.throws(() => core.argsFor(target, { preview: true, inputs: { name: ["a"] } }), /do not support generic dry runs/);
  target.spec.runnable = false;
  assert.throws(() => core.argsFor(target), /Choose a subcommand/);
});

test("built-in discovery keeps VMR root and member contexts separate", () => {
  const doc = inventory();
  doc.mode = "workspace";
  doc.commands = [{ name: "repos", path: ["repos"], runnable: true, params: [], children: [] }];
  const targets = core.availableBuiltins([{ inventory: doc, folder: "workspace" }]);
  const member = targets.find(t => t.name === "setup creds set");
  assert.equal(member.project, doc.projects[0]);
  assert.deepEqual(core.argsFor(member, { help: true }), ["--config", member.project.entry_file, "setup", "creds", "set", "--help"]);
  assert.deepEqual(core.argsFor(targets.find(t => t.name === "repos")), ["repos"]);
  assert.equal(targets.filter(t => t.name === "--help").length, 2);
});

test("discovery invokes an actual executable and parses stdout without a shell", async () => {
  const doc = inventory(process.cwd());
  const script = `if (process.argv.slice(1).join(' ') !== 'describe --json --configuration') process.exit(3); process.stdout.write(${JSON.stringify(JSON.stringify(doc))})`;
  assert.deepEqual(await core.readInventory({ executable: process.execPath, arguments: ["-e", script, "--"], timeout: 10 }, process.cwd()), doc);
});

test("missing executables, failing processes and timeouts are reported", async () => {
  await assert.rejects(core.readInventory({ executable: path.resolve("nonexistent-ptk-executable"), arguments: [], timeout: 1 }, process.cwd()), /executable not found/);
  await assert.rejects(core.readInventory({ executable: process.execPath, arguments: ["-e", "process.stderr.write('invalid project'); process.exit(2)", "--"], timeout: 10 }, process.cwd()), /invalid project/);
  await assert.rejects(core.readInventory({ executable: process.execPath, arguments: ["-e", "setTimeout(() => {}, 5000)", "--"], timeout: 0.1 }, process.cwd()), /timed out/);
});

test("cleanup flags precede commands and workflow variants are forwarded", () => {
  const job = target("job");
  assert.deepEqual(core.argsFor(job, { clean: true, variant: "large" }).slice(2), ["--variant", "large", "--clean", "run", "build"]);
  assert.deepEqual(core.argsFor(target("workflow"), { reRun: true, variant: "large", preview: true }).slice(2), ["--variant", "large", "--re-run", "workflow", "dry-run", "build"]);
  assert.throws(() => core.argsFor(job, { clean: true, reRun: true }), /Choose/);
  assert.deepEqual(core.argsFor(job, { clean: true, help: true }).slice(2), ["build", "--help"]);
});

test("uv launch arguments prevent implicit syncing on POSIX and Windows without changing explicit commands", () => {
  for (const executable of ["uv", "/tools/uv", "C:\\tools with spaces\\uv.EXE"]) {
    const settings = { executable, arguments: ["run", "--project", "folder with spaces", "ptk"] };
    assert.deepEqual(core.launchArgs(settings, ["version", "check"]), ["run", "--no-sync", "--project", "folder with spaces", "ptk", "version", "check"]);
    assert.deepEqual(settings.arguments, ["run", "--project", "folder with spaces", "ptk"]);
    assert.deepEqual(core.launchArgs({ executable, arguments: ["run", "--no-sync", "ptk"] }, ["describe", "--json", "--configuration"]), ["run", "--no-sync", "ptk", "describe", "--json", "--configuration"]);
  }
  assert.deepEqual(core.launchArgs({ executable: "ptk", arguments: [] }, ["version", "check"]), ["version", "check"]);
  assert.deepEqual(core.launchArgs({ executable: "uv", arguments: ["tool", "run", "ptk"] }, ["--help"]), ["tool", "run", "ptk", "--help"]);
});

test("watch filtering ignores installed resources but respects PTK-reported source files", () => {
  for (const [paths, root] of [[path, path.resolve("project")], [path.win32, "C:\\git\\project"]]) {
    const generated = paths.join(root, "config", ".gen.version.ptk.yml");
    assert.equal(core.ignoreConfigEvent(generated, [root], [generated]), true);
    for (const folder of [".venv", ".ptk", "custom-env/Lib/site-packages", "dist", ".github/ptk"]) {
      const file = paths.join(root, ...folder.split("/"), "example.ptk.yml");
      assert.equal(core.ignoreConfigEvent(file, [root]), true);
      assert.equal(core.ignoreConfigEvent(file, [root], [file]), false);
    }
    assert.equal(core.ignoreConfigEvent(paths.join(root, "config", "jobs", "new.ptk.yml"), [root]), false);
  }
});


test("configuration interface is required and unknown versions are rejected", () => {
  for (const configuration of [undefined, null, { version: 2 }, { version: 1 }]) {
    const doc = inventory();
    doc.projects[0].configuration = configuration;
    assert.throws(() => core.parseInventory(JSON.stringify(doc)), /configuration interface/);
  }
});

test("discovery does not retry without the configuration interface", async () => {
  const doc = inventory();
  const script = `if (process.argv.includes('--configuration')) { process.stderr.write('No such option: --configuration'); process.exit(2); } process.stdout.write(${JSON.stringify(JSON.stringify(doc))});`;
  await assert.rejects(core.readInventory({ executable: process.execPath, arguments: ["-e", script, "--"], timeout: 10 }, process.cwd()), /No such option: --configuration/);
});
