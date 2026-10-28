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
  const config = {};
  const forms = [];
  const formRequests = [];
  const opened = [];
  let editorActions;
  const watchers = [];
  const taskEnd = [];
  let outputShown = 0;
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
      createOutputChannel: () => ({ appendLine: line => logs.push(line), show() { outputShown++; }, dispose() {} }),
      registerTreeDataProvider: () => disposable(),
      showErrorMessage: async message => errors.push(message),
      showInformationMessage: async (message, ...actions) => { logs.push(message); return picks.shift()?.(actions); },
      showQuickPick: async (items, options) => picks.shift()?.(items, options),
      showInputBox: async () => inputs.shift(),
    },
    workspace: {
      isTrusted: trusted, workspaceFolders: folders,
      getConfiguration: () => ({ get: (key, fallback) => config[key] ?? fallback }),
      createFileSystemWatcher: pattern => {
        const callbacks = {};
        watchers.push({ pattern, callbacks });
        return Object.fromEntries([['dispose', () => {}], ...['Create', 'Change', 'Delete'].map(kind =>
          [`onDid${kind}`, callback => { callbacks[kind] = callback; return disposable(); }])]);
      },
      onDidChangeConfiguration: disposable, onDidChangeWorkspaceFolders: disposable, onDidGrantWorkspaceTrust: disposable,
    },
    commands: {
      registerCommand: (name, callback) => { commands.set(name, callback); return disposable(); },
      executeCommand: async () => {},
    },
    tasks: {
      executeTask: async task => { tasks.push(task); return task; },
      registerTaskProvider: (_type, provider) => { api.taskProvider = provider; return disposable(); },
      onDidEndTaskProcess: callback => { taskEnd.push(callback); return disposable(); },
    },
  };
  const context = {
    subscriptions: [],
    workspaceState: { get: key => state.get(key), update: async (key, value) => state.set(key, value) },
  };
  const controller = createController(api, context, (_api, _context, actions) => { editorActions = actions; return ({
    async parameters(target, options) { formRequests.push({ target, options }); return forms.shift()?.(target, options); },
    async open(uri, path = []) { opened.push({ uri, path }); },
    async openProject(owner, path = []) { opened.push({ owner, path }); },
    async children(element) { return [{ label: "Test field", configPath: [...element.configPath, "jobs"] }]; },
  }); });
  t.after(() => context.subscriptions.forEach(item => item.dispose()));
  const command = (name, element) => commands.get(`project-toolkit.${name}`)(element);
  const target = (kind = "job", index = 0) => ({ kind, name: "build", project: docs[index].projects[0], root: docs[index].projects[0].root });
  return { api, controller, command, target, context, state, tasks, errors, logs, picks, inputs, calls, config, watchers, taskEnd, outputShown: () => outputShown, forms, formRequests, opened, editorActions };
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
  h.picks.push(items => items.find(item => item.name === "large"));
  await h.command("selectVariant", h.target());
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
  h.forms.push((_target, options) => ({ params: { output_path: "folder with spaces;$(untouched)" }, preview: options.preview }));
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
  h.forms.push(() => ({ params: { output_path: "literal 'path'", verbose: "false" }, preview: false }));
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
  h.picks.push(items => items.find(item => item.name === "large"));
  await h.command("selectVariant", h.target("job", 0));
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
  assert.equal(h.tasks.length, 1);
  assert.equal(h.tasks[0].definition.kind, "validate");
  assert.equal(h.errors.length, 1);
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

test("refreshes are serialized and intermediate requests are coalesced", async t => {
  const h = harness(t);
  await h.controller.ready();
  let finishOld;
  h.api.workspace.workspaceFolders[0].name = "workspace";
  core.readInventory = () => new Promise(resolve => { finishOld = resolve; });
  const first = h.controller.refresh();
  await Promise.resolve();
  const latest = inventory();
  latest.projects[0].alias = "latest";
  let nextCalls = 0;
  core.readInventory = async () => { nextCalls++; return latest; };
  const second = h.controller.refresh();
  const third = h.controller.refresh();
  assert.equal(nextCalls, 0);
  finishOld(inventory());
  await Promise.all([first, second, third]);
  assert.equal(nextCalls, 1);
  assert.equal(h.controller.provider.getChildren()[0].children[0].label, "latest");
});

test("installed configuration copies do not refresh discovery and task completion recovers errors", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = harness(t);
  await h.controller.ready();
  const root = h.target().root;
  const watcher = h.watchers[0].callbacks;
  for (const directory of [".venv/Lib/site-packages/ptk/resources", ".ptk/venvs/test", "custom-env/Lib/site-packages/ptk", "_reports", "node_modules"]) {
    for (const callback of Object.values(watcher)) callback({ fsPath: path.join(root, directory, "example/.main.ptk.yml") });
  }
  t.mock.timers.tick(1000);
  await h.controller.ready();
  assert.equal(h.calls.length, 1);
  watcher.Change({ fsPath: h.target().project.entry_file });
  t.mock.timers.tick(350);
  await h.controller.ready();
  assert.equal(h.calls.length, 2);
  core.readInventory = async () => { throw new Error("Python environment temporarily unavailable"); };
  await h.controller.refresh();
  const warning = h.controller.provider.getChildren()[0];
  assert.equal(warning.command.command, "project-toolkit.showOutput");
  await h.command("showOutput");
  assert.equal(h.outputShown(), 1);
  assert.match(h.logs.at(-1), /temporarily unavailable/);
  core.readInventory = async () => inventory();
  for (const callback of h.taskEnd) callback({ execution: { task: { definition: { type: "project-toolkit", kind: "builtin" } } } });
  t.mock.timers.tick(350);
  await h.controller.ready();
  assert.equal(h.controller.provider.getChildren()[0].children[0].label, "demo");
  assert.equal(h.tasks.length, 0);
});

test("every task entry point uses the non-syncing uv launcher, including help and restored tasks", async t => {
  const h = harness(t);
  h.config.executable = "C:\\tools\\uv.EXE";
  h.config.arguments = ["run", "ptk"];
  await h.controller.ready();
  for (const kind of ["job", "workflow"]) {
    for (const command of ["run", "preview", "clean", "reRun", "showHelp", "openReport"]) await h.command(command, h.target(kind));
  }
  h.forms.push(() => ({ params: {}, preview: false }));
  await h.command("runWithParameters", h.target());
  for (const target of core.builtinTargets({ ...h.target(), folder: h.api.workspace.workspaceFolders[0] }, inventory().projects[0].commands)) {
    await h.command("showHelp", target);
  }
  await h.command("runBuiltin", { ...h.target("builtin"), name: "version check" });
  h.picks.push(() => []);
  await h.command("runBuiltinWithParameters", { ...h.target("builtin"), name: "version check" });
  for (const task of h.tasks) {
    assert.deepEqual(task.execution.args.slice(0, 3), ["run", "--no-sync", "ptk"]);
    assert.equal(task.execution.options.env, undefined); // Do not leak UV_NO_SYNC into job steps.
    const restored = await h.api.taskProvider.resolveTask(task);
    assert.deepEqual(restored.execution.args, task.execution.args);
  }
  await h.command("showVariant", { ...h.target(), name: "large" });
  await h.command("validate", h.target());
  for (const task of [...h.tasks, ...await h.api.taskProvider.provideTasks()]) {
    assert.deepEqual(task.execution.args.slice(0, 3), ["run", "--no-sync", "ptk"]);
  }
  assert.deepEqual(h.errors, []);
});

test("job actions expose icons with tooltip titles in the sidebar", () => {
  const manifest = require("../package.json").contributes;
  for (const name of ["run", "preview", "runWithParameters", "showHelp", "openReport"]) {
    const command = `project-toolkit.${name}`;
    const entry = manifest.commands.find(entry => entry.command === command);
    assert.ok(entry.icon && entry.title);
    assert.match(manifest.menus["view/item/context"].find(entry => entry.command === command).group, /^inline@/);
  }
});

test("tree omits duplicate run and report commands in repositories and workspaces", async t => {
  const doc = inventory();
  doc.mode = "workspace";
  doc.commands = builtinCommands();
  doc.workflows = [{ name: "all" }];
  const h = harness(t, [doc]);
  await h.controller.ready();
  const root = h.controller.provider.getChildren()[0];
  const project = root.children.find(node => node.project);
  for (const owner of [root, project]) {
    const builtins = owner.children.find(node => node.label === "Built-in commands");
    assert.deepEqual(builtins.children.map(node => node.label), ["CLI help", "help", "version", "workflow", "setup"]);
    assert.deepEqual(builtins.children.find(node => node.label === "workflow").children.map(node => node.label), ["list", "show"]);
  }
  for (const label of ["Jobs", "Workflows"]) {
    const node = project.children.find(node => node.label === label).children[0];
    assert.equal(node.contextValue, `${node.kind}-report`);
  }
  assert.equal(root.children[0].children[0].contextValue, "workflow-report");
  // Removing the duplicate rows does not remove CLI operations or saved tasks.
  await h.command("runBuiltin", { ...h.target("builtin"), name: "run" });
  assert.equal(h.tasks[0].execution.args.at(-1), "run");
});

test("report actions target job variants and aggregate workflows without running or prompting", async t => {
  const doc = inventory();
  doc.ci = true;
  doc.mode = "workspace";
  doc.commands = builtinCommands();
  doc.workflows = [{ name: "all" }];
  doc.projects[0].jobs[0].params[0].required = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.picks.push(items => items.find(item => item.name === "large"));
  await h.command("selectVariant", h.target());
  h.api.window.showQuickPick = h.api.window.showInputBox = () => assert.fail("Report actions must not prompt for run parameters");
  await h.command("openReport", h.target());
  await h.command("openReport", h.target("workflow"));
  await h.command("openReport", { kind: "workflow", name: "all", root: doc.root });
  assert.deepEqual(h.tasks[0].execution.args.slice(2), ["--variant", "large", "report", "open", "--if-exists", "--", "build"]);
  assert.deepEqual(h.tasks[1].execution.args.slice(2), ["workflow", "report", "--if-exists", "--", "build"]);
  assert.deepEqual(h.tasks[2].execution.args, ["workflow", "report", "--if-exists", "--", "all"]);
  for (const task of h.tasks) {
    assert.equal(task.definition.report, true);
    assert.deepEqual((await h.api.taskProvider.resolveTask(task)).execution.args, task.execution.args);
  }
  assert.deepEqual(h.errors, []);
  const stale = h.target("workflow");
  doc.projects[0].commands.find(spec => spec.name === "workflow").children = [];
  await h.controller.refresh();
  await h.command("openReport", stale);
  assert.equal(h.tasks.length, 3);
  assert.equal(await h.api.taskProvider.resolveTask(h.tasks[1]), undefined);
  assert.match(h.errors.at(-1), /Report opening is unavailable/);
  h.api.workspace.isTrusted = false;
  await h.command("openReport", h.target());
  assert.equal(h.tasks.length, 3);
  assert.match(h.errors.at(-1), /Trust this workspace/);
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


test("configuration tree follows PTK schema and opens logical fields", async t => {
  const h = harness(t);
  await h.controller.ready();
  const config = h.controller.provider.getChildren()[0].children[0].children.find(node => node.label === "Configuration");
  const jobs = config.children.find(node => node.label === "jobs");
  assert.deepEqual(jobs.configPath, ["jobs"]);
  assert.ok(!config.children.some(node => node.configFile));
  await h.command("openConfig", jobs);
  assert.deepEqual(h.opened[0].path, ["jobs"]);
});

test("parameter form can choose a preview and does not override omitted defaults", async t => {
  const h = harness(t);
  await h.controller.ready();
  h.forms.push(() => ({ params: {}, preview: true }));
  await h.command("runWithParameters", h.target());
  assert.equal(h.formRequests[0].options.variant, "small");
  assert.equal(h.tasks[0].definition.preview, true);
  assert.equal(h.tasks[0].definition.params, undefined);
  assert.ok(h.tasks[0].execution.args.includes("dry-run"));
});

test("a job removed while its parameter form is open cannot launch", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.forms.push(async () => {
    doc.projects[0].jobs = [];
    await h.controller.refresh();
    return { params: {}, preview: false };
  });
  await h.command("runWithParameters", h.target());
  assert.equal(h.tasks.length, 0);
  assert.match(h.errors[0], /no longer available/);
});

test("parameters changed while the form is open are validated before launch", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.forms.push(async () => {
    doc.projects[0].jobs[0].params[0].required = true;
    await h.controller.refresh();
    return { params: {}, preview: false };
  });
  await h.command("runWithParameters", h.target());
  assert.equal(h.tasks.length, 0);
  assert.match(h.errors[0], /output_path: enter a value/);
});


test("configuration files and validation remain available after an invalid save breaks discovery", async t => {
  const h = harness(t);
  await h.controller.ready();
  const file = h.target().project.config_files[0];
  core.readInventory = async () => { throw new Error("invalid configuration"); };
  await h.controller.refresh();
  await h.controller.refresh();
  const warning = h.controller.provider.getChildren()[0];
  assert.ok(warning.children.some(node => node.label === "Validate configuration"));
  await h.editorActions.validate({ fsPath: file });
  assert.deepEqual(h.tasks[0].execution.args.slice(-3), ["setup", "config", "validate"]);
  assert.equal(h.tasks[0].execution.args[1], h.target().project.entry_file);
});


test("logical configuration paths have unique identities across projects", async t => {
  const h = harness(t, [inventory(path.resolve("first")), inventory(path.resolve("second"))]);
  await h.controller.ready();
  const fields = h.controller.provider.getChildren().map(root => root.children[0].children.find(node => node.label === "Configuration").children[0]);
  assert.notEqual(fields[0].id, fields[1].id);
});

test("jobs and workflows select variants independently with no Variants group", async t => {
  const h = harness(t);
  await h.controller.ready();
  h.picks.push(items => items.find(item => item.name === "large"));
  await h.command("selectVariant", h.target());
  await h.command("run", h.target());
  await h.command("run", h.target("workflow"));
  assert.equal(h.tasks[0].definition.variant, "large");
  assert.equal(h.tasks[1].definition.variant, "small");
  const groups = h.controller.provider.getChildren()[0].children[0].children;
  assert.ok(!groups.some(node => node.label === "Variants"));
  assert.match(groups.find(node => node.label === "Jobs").children[0].description, /large/);
});

test("validation on an empty workspace offers init using an explicit config directory", async t => {
  const doc = inventory(); doc.projects = [];
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.picks.push(actions => actions[0]); h.inputs.push("configuration");
  await h.command("validate");
  assert.ok(h.logs.some(message => /No PTK project found/.test(message)));
  assert.deepEqual(h.tasks[0].execution.args, ["setup", "init", "--config-dir", "configuration", "--", doc.root]);
});

test("initial invalid project exposes diagnostics and validation without prior inventory", async t => {
  const doc = inventory(); doc.projects[0].error = "invalid event route";
  doc.projects[0].diagnostics = [{ file: doc.projects[0].entry_file, line: 4, message: "invalid event route" }];
  const h = harness(t, [doc]); await h.controller.ready();
  const node = h.controller.provider.getChildren()[0].children[0];
  assert.equal(node.description, "configuration error");
  await h.command("validate", node);
  assert.equal(h.tasks[0].definition.kind, "validate");
});
