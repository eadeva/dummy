"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const core = require("../src/core");
const { createController } = require("../src/extension");
const { inventory, builtinCommands } = require("./fixtures");

function harness(t, docs = [inventory()], trusted = true) {
  const commands = new Map();
  const state = new Map();
  const tasks = [];
  const errors = [];
  const logs = [];
  const picks = [];
  const inputs = [];
  const calls = [];
  const disposable = () => ({ dispose() {} });
  const folder = doc => ({ name: path.basename(doc.root), uri: { scheme: "file", fsPath: doc.root } });
  const folders = docs.map(folder);
  t.mock.method(core, "readInventory", async (settings, cwd) => {
    calls.push({ settings, cwd });
    return structuredClone(docs.find(doc => doc.root === cwd));
  });
  class EventEmitter { event = () => disposable(); fire() {} dispose() {} }
  class Task {
    constructor(definition, scope, name, source, execution, problemMatchers) {
      Object.assign(this, { definition, scope, name, source, execution, problemMatchers });
    }
  }
  class ProcessExecution {
    constructor(process, args, options) { Object.assign(this, { process, args, options }); }
  }
  const api = {
    EventEmitter, Task, ProcessExecution,
    TreeItem: class { constructor(label, state) { Object.assign(this, { label, state }); } },
    ThemeIcon: class {}, ThemeColor: class {}, TreeItemCollapsibleState: { Expanded: 2, Collapsed: 1, None: 0 },
    TaskRevealKind: { Always: 1 }, TaskPanelKind: { Dedicated: 2 },
    Uri: { file: fsPath => ({ scheme: "file", fsPath }) },
    window: {
      createOutputChannel: () => ({ appendLine: line => logs.push(line), dispose() {} }),
      registerTreeDataProvider: () => disposable(),
      showErrorMessage: async message => errors.push(message),
      showQuickPick: async (items, options) => picks.shift()?.(items, options),
      showInputBox: async () => inputs.shift(),
    },
    workspace: {
      isTrusted: trusted, workspaceFolders: folders,
      getConfiguration: () => ({ get: (_key, fallback) => fallback }),
      createFileSystemWatcher: () => ({ dispose() {}, onDidCreate: disposable, onDidChange: disposable, onDidDelete: disposable }),
      onDidChangeConfiguration: disposable, onDidChangeWorkspaceFolders: disposable, onDidGrantWorkspaceTrust: disposable,
    },
    commands: {
      registerCommand: (name, callback) => { commands.set(name, callback); return disposable(); },
      executeCommand: async () => {},
    },
    tasks: {
      executeTask: async task => { tasks.push(task); return task; },
      registerTaskProvider: (_type, provider) => { api.taskProvider = provider; return disposable(); },
    },
  };
  const context = {
    subscriptions: [],
    workspaceState: { get: key => state.get(key), update: async (key, value) => state.set(key, value) },
  };
  const controller = createController(api, context);
  t.after(() => context.subscriptions.forEach(item => item.dispose()));
  const command = (name, element) => commands.get(`project-toolkit.${name}`)(element);
  const target = (kind = "job", index = 0) => ({ kind, name: "build", project: docs[index].projects[0], root: docs[index].projects[0].root });
  return { api, controller, command, target, context, state, tasks, errors, logs, picks, inputs, calls };
}

test("activation discovers projects and runs jobs as processes with global variants", async t => {
  const h = harness(t);
  await h.controller.ready();
  const tree = h.controller.provider.getChildren();
  assert.equal(tree[0].children[0].label, "demo");
  await h.command("run", h.target());
  const task = h.tasks[0];
  assert.equal(task.execution.process, "ptk");
  assert.deepEqual(task.execution.args, ["--config", h.target().project.entry_file, "--variant", "small", "run", "build"]);
  assert.equal(task.execution.options.cwd, h.target().root);
  assert.deepEqual(h.errors, []);
});

test("untrusted workspaces never discover or run PTK", async t => {
  const h = harness(t, [inventory()], false);
  await h.controller.ready();
  await h.command("run", h.target());
  assert.equal(h.calls.length, 0);
  assert.equal(h.tasks.length, 0);
  assert.match(h.errors[0], /Trust this workspace/);
  assert.deepEqual(await h.api.taskProvider.provideTasks(), []);
});

test("variant choices are workspace state only and can return to the configured default", async t => {
  const h = harness(t);
  await h.controller.ready();
  await h.command("selectVariant", { ...h.target(), name: "large" });
  await h.command("run", h.target());
  assert.equal(h.tasks[0].definition.variant, "large");
  h.picks.push(items => items.find(item => item.reset));
  await h.command("selectVariant", h.target());
  await h.command("run", h.target());
  assert.equal(h.tasks[1].definition.variant, "small");
  assert.equal(h.target().project.default_variant, "small");
});

test("parameterized previews stay previews after task restoration", async t => {
  const doc = inventory();
  doc.projects[0].jobs[0].params[0].required = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.inputs.push("folder with spaces;$(untouched)");
  await h.command("preview", h.target());
  const original = h.tasks[0];
  const restored = await h.api.taskProvider.resolveTask(original);
  assert.equal(restored.definition, original.definition);
  assert.deepEqual(restored.execution.args, original.execution.args);
  assert.equal(restored.definition.preview, true);
  assert.equal(restored.definition.params.output_path, "folder with spaces;$(untouched)");
  assert.equal(restored.execution.args.includes("run"), false);
  assert.equal(restored.execution.args.includes("dry-run"), true);
});

test("required parameter cancellation does not execute anything", async t => {
  const doc = inventory();
  doc.projects[0].jobs[0].params[0].required = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("run", h.target());
  assert.equal(h.tasks.length, 0);
  assert.equal((await h.api.taskProvider.provideTasks()).some(task => task.definition.kind === "job"), false);
  assert.equal(await h.api.taskProvider.resolveTask({ definition: { ...h.target(), params: {} } }), undefined);
});

test("optional typed parameter overrides retain booleans and literal text", async t => {
  const h = harness(t);
  await h.controller.ready();
  h.picks.push(items => items, items => items.find(item => item === "false"));
  h.inputs.push("literal 'path'");
  await h.command("runWithParameters", h.target());
  assert.deepEqual(h.tasks[0].execution.args.slice(-4), ["--param", "output_path=literal 'path'", "--param", "verbose=false"]);
  assert.deepEqual((await h.api.taskProvider.resolveTask(h.tasks[0])).execution.args, h.tasks[0].execution.args);
});

test("workflow and job name collisions dispatch explicitly and CI allows previews only", async t => {
  const doc = inventory();
  doc.ci = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("run", h.target("workflow"));
  assert.equal(h.tasks.length, 0);
  assert.match(h.errors[0], /locally only/);
  await h.command("preview", h.target("workflow"));
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["--variant", "small", "workflow", "dry-run", "build"]);
  const restored = await h.api.taskProvider.resolveTask(h.tasks[0]);
  assert.deepEqual(restored.execution.args, h.tasks[0].execution.args);
  assert.equal((await h.api.taskProvider.provideTasks()).some(task => task.definition.kind === "workflow"), false);
});

test("multi-root projects keep independent variant selections", async t => {
  const h = harness(t, [inventory(path.resolve("first")), inventory(path.resolve("second"))]);
  await h.controller.ready();
  await h.command("selectVariant", { ...h.target("job", 0), name: "large" });
  await h.command("run", h.target("job", 1));
  await h.command("run", h.target("job", 0));
  assert.equal(h.tasks[0].definition.variant, "small");
  assert.equal(h.tasks[1].definition.variant, "large");
  assert.notEqual(h.tasks[0].execution.options.cwd, h.tasks[1].execution.options.cwd);
});

test("refreshed permission changes reject stale tree commands", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  const oldTarget = h.target();
  doc.projects[0].jobs = [];
  await h.controller.refresh();
  await h.command("run", oldTarget);
  assert.equal(h.tasks.length, 0);
  assert.match(h.errors[0], /no longer available/);
});

test("report permissions and capability checks apply to palette commands", async t => {
  const doc = inventory();
  doc.projects[0].capabilities.reports = false;
  doc.projects[0].capabilities.validate = false;
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("openReport", h.target());
  await h.command("validate", h.target());
  assert.equal(h.tasks.length, 0);
  assert.equal(h.errors.length, 2);
});

test("workspace workflows use the workspace root without a member config", async t => {
  const doc = inventory();
  doc.mode = "workspace";
  doc.workflows = [{ name: "all" }];
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("preview", { kind: "workflow", name: "all", root: doc.root });
  assert.deepEqual(h.tasks[0].execution.args, ["workflow", "dry-run", "all"]);
});

test("the newest refresh wins when discovery completes out of order", async t => {
  const h = harness(t);
  await h.controller.ready();
  let finishOld;
  h.api.workspace.workspaceFolders[0].name = "workspace";
  core.readInventory = () => new Promise(resolve => { finishOld = resolve; });
  const first = h.controller.refresh();
  const latest = inventory();
  latest.projects[0].alias = "latest";
  core.readInventory = async () => latest;
  await h.controller.refresh();
  finishOld(inventory());
  await first;
  assert.equal(h.controller.provider.getChildren()[0].children[0].label, "latest");
});

test("job actions expose icons with tooltip titles in the sidebar", () => {
  const manifest = require("../package.json").contributes;
  for (const name of ["run", "preview", "runWithParameters", "showHelp"]) {
    const command = `project-toolkit.${name}`;
    const entry = manifest.commands.find(entry => entry.command === command);
    assert.ok(entry.icon && entry.title);
    assert.match(manifest.menus["view/item/context"].find(entry => entry.command === command).group, /^inline@/);
  }
});

test("help runs without variant or required-parameter prompts and survives task restoration", async t => {
  const doc = inventory();
  doc.projects[0].default_variant = undefined;
  doc.projects[0].jobs[0].params[0].required = true;
  doc.ci = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.api.window.showQuickPick = h.api.window.showInputBox = () => assert.fail("Help must not prompt");
  await h.command("showHelp", h.target());
  await h.command("showHelp", h.target("workflow"));
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["build", "--help"]);
  assert.deepEqual(h.tasks[1].execution.args.slice(2), ["workflow", "run", "build", "--help"]);
  for (const task of h.tasks) {
    assert.deepEqual((await h.api.taskProvider.resolveTask(task)).execution.args, task.execution.args);
  }
  assert.deepEqual(h.errors, []);
});

test("built-ins form a collapsible command tree with CLI help and credential actions", async t => {
  const h = harness(t);
  await h.controller.ready();
  const project = h.controller.provider.getChildren()[0].children[0];
  const builtins = project.children.find(node => node.label === "Built-in commands");
  const setup = builtins.children.find(node => node.label === "setup");
  const creds = setup.children.find(node => node.label === "creds");
  assert.equal(h.controller.provider.getTreeItem(setup).state, h.api.TreeItemCollapsibleState.Collapsed);
  assert.equal(creds.contextValue, "builtin-group");
  assert.deepEqual(creds.children.map(node => node.label), ["list", "set"]);
  const help = builtins.children.find(node => node.label === "CLI help");
  assert.doesNotThrow(() => JSON.stringify(help.command));
  await h.command("showHelp", help.command.arguments[0]);
  await h.command("showHelp", creds);
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["--help"]);
  assert.deepEqual(h.tasks[1].execution.args.slice(2), ["setup", "creds", "--help"]);
});

test("built-in required input cancellation prevents execution; secret entry stays in the terminal", async t => {
  const h = harness(t);
  await h.controller.ready();
  const target = { ...h.target("builtin"), name: "setup creds set" };
  await h.command("runBuiltin", target);
  assert.equal(h.tasks.length, 0);
  h.inputs.push("service name");
  await h.command("runBuiltin", target);
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["setup", "creds", "set", "--", "service name"]);
  assert.deepEqual(h.tasks[0].definition.inputs, { name: ["service name"] });
  assert.equal(h.tasks[0].presentationOptions.focus, true);
  assert.deepEqual((await h.api.taskProvider.resolveTask(h.tasks[0])).execution.args, h.tasks[0].execution.args);
  assert.equal((await h.api.taskProvider.provideTasks()).some(task => task.definition.kind === "builtin"), false);
});

test("built-in option prompts preserve choices and positional values", async t => {
  const h = harness(t);
  await h.controller.ready();
  h.picks.push(items => items, items => items.find(item => item === "json"));
  h.inputs.push("project.name");
  await h.command("runBuiltinWithParameters", { ...h.target("builtin"), name: "setup config show" });
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["setup", "config", "show", "--format=json", "--", "project.name"]);
  assert.deepEqual(h.errors, []);
});

test("built-in execution rechecks workspace trust and refreshed command permissions", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  const target = { ...h.target("builtin"), name: "setup creds list" };
  h.api.workspace.isTrusted = false;
  await h.command("runBuiltin", target);
  assert.match(h.errors.pop(), /Trust this workspace/);
  h.api.workspace.isTrusted = true;
  doc.projects[0].commands = [];
  await h.controller.refresh();
  await h.command("runBuiltin", target);
  assert.match(h.errors.pop(), /no longer available/);
  assert.equal(h.tasks.length, 0);
});

test("VMR root built-ins omit member configuration and older CLIs retain CLI help", async t => {
  const doc = inventory();
  doc.mode = "workspace";
  doc.commands = builtinCommands();
  delete doc.projects[0].commands;
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("runBuiltin", { kind: "builtin", root: doc.root, name: "setup creds list" });
  assert.deepEqual(h.tasks[0].execution.args, ["setup", "creds", "list"]);
  const project = h.controller.provider.getChildren()[0].children[0];
  const commands = project.children.find(node => node.label === "Built-in commands").children;
  assert.ok(commands.some(node => /Update PTK/.test(node.label)));
  await h.command("showHelp", commands[0]);
  assert.deepEqual(h.tasks[1].execution.args, ["--config", doc.projects[0].entry_file, "--help"]);
});

test("clean bypasses required parameters and survives saved-task restoration", async t => {
  const doc = inventory();
  doc.projects[0].jobs[0].params[0].required = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("clean", h.target());
  assert.equal(h.tasks.length, 1);
  assert.equal(h.tasks[0].definition.clean, true);
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["--variant", "small", "--clean", "run", "build"]);
  const restored = await h.api.taskProvider.resolveTask(h.tasks[0]);
  assert.deepEqual(restored.execution.args, h.tasks[0].execution.args);
  await h.command("reRun", h.target("workflow"));
  assert.equal(h.tasks[1].definition.reRun, true);
  assert.deepEqual(h.tasks[1].execution.args.slice(2), ["--variant", "small", "--re-run", "workflow", "run", "build"]);
});
