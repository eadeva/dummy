"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const core = require("../src/core");
const { createController } = require("../src/extension");
const { inventory, builtinCommands, builtinParam } = require("./fixtures");

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
  const changedElements = [];
  let checkboxListener, treeOptions;
  let outputShown = 0, treeChanges = 0;
  const disposable = () => ({ dispose() {} });
  const folder = doc => ({ name: path.basename(doc.root), uri: { scheme: "file", fsPath: doc.root } });
  const folders = docs.map(folder);
  t.mock.method(core, "readInventory", async (settings, cwd) => {
    calls.push({ settings, cwd });
    return structuredClone(docs.find(doc => doc.root === cwd));
  });
  class EventEmitter { event = () => disposable(); fire(element) { treeChanges++; changedElements.push(element); } dispose() {} }
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
    ThemeIcon: class { constructor(id, color) { Object.assign(this, { id, color }); } },
    ThemeColor: class { constructor(id) { this.id = id; } }, TreeItemCollapsibleState: { Expanded: 2, Collapsed: 1, None: 0 },
    TreeItemCheckboxState: { Unchecked: 0, Checked: 1 },
    TaskRevealKind: { Always: 1 }, TaskPanelKind: { Dedicated: 2 },
    Uri: { file: fsPath => ({ scheme: "file", fsPath }) },
    window: {
      createOutputChannel: () => ({ appendLine: line => logs.push(line), show() { outputShown++; }, dispose() {} }),
      createTreeView: (_id, options) => { treeOptions = options; return { ...disposable(), onDidChangeCheckboxState(callback) { checkboxListener = callback; return disposable(); } }; },
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
  }); });
  t.after(() => context.subscriptions.forEach(item => item.dispose()));
  const command = (name, element) => commands.get(`project-toolkit.${name}`)(element);
  const target = (kind = "job", index = 0) => ({ kind, name: "build", project: docs[index].projects[0], root: docs[index].projects[0].root });
  return { api, controller, command, target, context, state, tasks, errors, logs, picks, inputs, calls, config, watchers, taskEnd, outputShown: () => outputShown, forms, formRequests, opened, editorActions, treeChanges: () => treeChanges,
    checkbox: items => checkboxListener({ items }), treeOptions: () => treeOptions, changedElements };
}

function jobNode(h, label = "Jobs") {
  return h.controller.provider.getChildren()[0].children[0].children.find(node => node.label === label).children[0];
}

async function selectAllJobVariants(h) {
  const node = jobNode(h);
  await h.checkbox(node.children.filter(item => item.variantName).map(item => [item, 1]));
  return node;
}

test("job variants launch concurrently with independent task identities and terminals", async t => {
  const h = harness(t);
  await h.controller.ready();
  const node = await selectAllJobVariants(h);
  const releases = [];
  t.mock.method(h.api.tasks, "executeTask", task => {
    h.tasks.push(task);
    return new Promise(resolve => releases.push(() => resolve(task)));
  });
  const run = h.command("run", node);
  await new Promise(resolve => setImmediate(resolve));
  try {
    assert.equal(h.tasks.length, 2, "both tasks start before either launch promise resolves");
    assert.deepEqual(h.tasks.map(task => task.definition.variant), ["small", "large"]);
    assert.equal(new Set(h.tasks.map(task => task.name)).size, 2);
    for (const task of h.tasks) {
      assert.ok(task.name.includes(`[${task.definition.variant}]`));
      assert.equal(task.presentationOptions.panel, h.api.TaskPanelKind.Dedicated);
    }
  } finally { releases.forEach(release => release()); await run; }
  const automatic = (await h.api.taskProvider.provideTasks()).filter(task => task.definition.kind === "job");
  assert.deepEqual(automatic.map(task => task.definition.variant), ["small", "large"]);
  // Rerunning a task keeps its own variant after the checkbox selection changes.
  await h.checkbox([[node.children[0], 1]]);
  for (const task of h.tasks) {
    const resolved = await h.api.taskProvider.resolveTask(task);
    assert.deepEqual(resolved.execution.args, task.execution.args);
  }
});

test("multi-variant parameter overrides are collected once and cancellation launches nothing", async t => {
  const h = harness(t);
  await h.controller.ready();
  const node = await selectAllJobVariants(h);
  h.forms.push((_target, options) => {
    assert.deepEqual(options.variants, ["small", "large"]);
    return { params: { output_path: "folder with spaces" }, preview: true };
  });
  await h.command("runWithParameters", node);
  assert.equal(h.formRequests.length, 1);
  assert.equal(h.tasks.length, 2);
  for (const task of h.tasks) {
    assert.equal(task.definition.preview, true);
    assert.deepEqual(task.definition.params, { output_path: "folder with spaces" });
  }
  h.forms.push(() => undefined);
  await h.command("runWithParameters", node);
  assert.equal(h.tasks.length, 2);
});

test("multi-variant actions preflight the whole selection and retain cleanup/report semantics", async t => {
  const doc = inventory(), h = harness(t, [doc]);
  await h.controller.ready();
  const node = await selectAllJobVariants(h);
  for (const [command, property] of [["preview", "preview"], ["clean", "clean"], ["reRun", "reRun"], ["openReport", "report"]]) {
    const before = h.tasks.length;
    await h.command(command, node);
    assert.deepEqual(h.tasks.slice(before).map(task => [task.definition.variant, task.definition[property]]), [["small", true], ["large", true]]);
  }
  const before = h.tasks.length;
  h.forms.push(async () => {
    doc.projects[0].variants = doc.projects[0].variants.filter(item => item.name !== "large");
    await h.controller.refresh();
    return { params: {}, preview: false };
  });
  await h.command("runWithParameters", node);
  assert.equal(h.tasks.length, before);
  assert.match(h.errors.at(-1), /selected variant is no longer available/);
});

test("job quick pick supports multiple checks, defaults and cancellation; workflows stay single", async t => {
  const h = harness(t);
  await h.controller.ready();
  h.picks.push((items, options) => { assert.equal(options.canPickMany, true); return items; });
  await h.command("selectVariant", h.target());
  await h.command("run", h.target());
  assert.deepEqual(h.tasks.map(task => task.definition.variant), ["small", "large"]);
  h.picks.push(() => undefined);
  await h.command("selectVariant", h.target());
  assert.match(h.controller.provider.getTreeItem(jobNode(h)).description, /small, large/);
  const workflow = jobNode(h, "Workflows");
  await h.checkbox(workflow.children.filter(item => item.variantName).map(item => [item, 1]));
  assert.equal(workflow.children.filter(item => h.controller.provider.getTreeItem(item).checkboxState.state === 1).length, 1);
  await h.checkbox([[jobNode(h).children[0], 1]]);
  assert.equal(h.controller.provider.getTreeItem(jobNode(h)).description, "small");
});

test("configuration tree uses meaningful root order and scalar fields before collections", async t => {
  const doc = inventory();
  doc.projects[0].configuration.schema = require("../media/config-schema.json");
  doc.projects[0].configuration.value = {
    jobs: { build: { env: {}, steps: [{ zeta: "echo first" }, { alpha: "echo second" }], help: "Build", audience: "all" } },
    project: { components: {}, description: "Demo", name: "Project" }, repository: { config_path: "config", alias: "demo" },
  };
  const h = harness(t, [doc]);
  await h.controller.ready();
  const config = h.controller.provider.getChildren()[0].children[0].children.find(item => item.label === "Configuration");
  assert.deepEqual(config.children.slice(0, 10).map(item => item.label), ["schema_version", "ptk_version", "virtual_monorepo", "repository", "project", "variants", "Components", "jobs", "workflows", "vars"]);
  const job = config.children.find(item => item.label === "jobs").children[0];
  assert.deepEqual(job.children.map(item => item.label), ["help", "audience", "env", "steps"]);
  assert.deepEqual(job.children.at(-1).children.map(item => item.configPath.at(-1)), [0, 1]);
});

test("job variant checkboxes keep multiple choices without discovery or changing configuration", async t => {
  const h = harness(t);
  await h.controller.ready();
  assert.equal(h.treeOptions().manageCheckboxStateManually, true);
  const node = jobNode(h), choices = node.children;
  const checked = () => choices.filter(item => h.controller.provider.getTreeItem(item).checkboxState.state === 1).map(item => item.label);
  assert.deepEqual(checked(), ["Use project default"]);
  assert.ok(choices.every(item => !item.project.variants.find(v => v.name === item.variantName)?.abstract));
  const calls = h.calls.length;
  const before = JSON.stringify(node.project.configuration);
  await h.checkbox([[choices.find(item => item.variantName === "large"), 1]]);
  assert.deepEqual(h.changedElements.at(-1), [node]);
  assert.deepEqual(checked(), ["large"]);
  assert.match(h.controller.provider.getTreeItem(node).description, /large/);
  await h.command("run", node);
  assert.equal(h.tasks[0].definition.variant, "large");
  assert.equal(h.calls.length, calls);
  assert.equal(JSON.stringify(node.project.configuration), before);
  await h.checkbox([[choices.find(item => item.variantName === "small"), 1]]);
  assert.deepEqual(checked(), ["small", "large"]);
  await h.command("run", node);
  assert.deepEqual(h.tasks.slice(1).map(task => task.definition.variant), ["large", "small"]);
  await h.checkbox([[choices.find(item => item.variantName === "large"), 0]]);
  assert.deepEqual(checked(), ["small"]);
  await h.checkbox([[choices.find(item => item.variantName === "small"), 0]]);
  assert.deepEqual(checked(), ["Use project default"]);
  await h.command("run", node);
  assert.equal(h.tasks.at(-1).definition.variant, "small");
});

test("checkbox selections remain independent for jobs, workflows and repositories", async t => {
  const h = harness(t, [inventory(), inventory(path.resolve("second"))]);
  await h.controller.ready();
  const job = jobNode(h), workflow = jobNode(h, "Workflows");
  await h.checkbox([[job.children.find(item => item.variantName === "large"), 1]]);
  await h.command("run", workflow);
  await h.command("run", h.target("job", 1));
  assert.deepEqual(h.tasks.map(task => task.definition.variant), ["small", "small"]);
  assert.equal(h.controller.provider.getTreeItem(workflow.children[0]).checkboxState.state, 1);
  const refreshed = jobNode(h);
  assert.deepEqual(refreshed.children.map(item => item.id), job.children.map(item => item.id));
  assert.equal(h.controller.provider.getTreeItem(refreshed.children.find(item => item.variantName === "large")).checkboxState.state, 1);
});

test("checkboxes serialize rapid changes and reject removed or abstract variants", async t => {
  const doc = inventory(), h = harness(t, [doc]);
  await h.controller.ready();
  const choices = jobNode(h).children;
  await Promise.all([h.checkbox([[choices.find(item => item.variantName === "large"), 1]]), h.checkbox([[choices.find(item => item.variantName === "small"), 1]])]);
  await h.command("run", h.target());
  assert.deepEqual(h.tasks.map(task => task.definition.variant), ["large", "small"]);
  doc.projects[0].variants.find(item => item.name === "large").abstract = true;
  await h.controller.refresh();
  await h.checkbox([[choices.find(item => item.variantName === "large"), 1]]);
  assert.match(h.errors[0], /variant is no longer available/);
  assert.equal(jobNode(h).children.some(item => item.variantName === "large"), false);
});

test("no default keeps a visible reset choice and a stale saved variant falls back safely", async t => {
  const doc = inventory();
  delete doc.projects[0].default_variant;
  const h = harness(t, [doc]);
  await h.controller.ready();
  const node = jobNode(h);
  h.state.set(`variant:${node.project.entry_file}:job:${node.name}`, "removed");
  assert.equal(h.controller.provider.getTreeItem(node.children[0]).checkboxState.state, 1);
  assert.equal(node.children[0].description, "No default configured");
  await h.checkbox([[node.children[0], 0]]);
  assert.equal(h.controller.provider.getTreeItem(node.children[0]).checkboxState.state, 1);
  h.api.workspace.isTrusted = false;
  await h.checkbox([[node.children[1], 1]]);
  assert.match(h.errors[0], /Trust this workspace/);
});

test("activation discovers projects and runs jobs as processes with global variants", async t => {
  const h = harness(t);
  await h.controller.ready();
  const tree = h.controller.provider.getChildren();
  assert.equal(tree[0].children[0].label, "demo");
  await h.command("run", h.target());
  const task = h.tasks[0];
  assert.equal(task.execution.process, "ptk");
  assert.deepEqual(task.execution.args, ["--variant", "small", "run", "build"]);
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
  h.picks.push(items => items.filter(item => item.name === "large"));
  await h.command("selectVariant", h.target());
  await h.command("run", h.target());
  assert.equal(h.tasks[0].definition.variant, "large");
  h.picks.push(() => []);
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
  assert.equal(restored.execution.args.includes("run"), true);
  assert.equal(restored.execution.args.includes("--dry-run"), true);
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
  assert.deepEqual(h.tasks[0].execution.args, ["--variant", "small", "workflow", "run", "build", "--dry-run"]);
  const restored = await h.api.taskProvider.resolveTask(h.tasks[0]);
  assert.deepEqual(restored.execution.args, h.tasks[0].execution.args);
  assert.equal((await h.api.taskProvider.provideTasks()).some(task => task.definition.kind === "workflow"), false);
});

test("multi-root projects keep independent variant selections", async t => {
  const h = harness(t, [inventory(path.resolve("first")), inventory(path.resolve("second"))]);
  await h.controller.ready();
  h.picks.push(items => items.filter(item => item.name === "large"));
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
  doc.workflows = [{ name: "all", run_options: [], command: ["workflow", "run", "all"] }];
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("preview", { kind: "workflow", name: "all", root: doc.root });
  assert.deepEqual(h.tasks[0].execution.args, ["workflow", "run", "all", "--dry-run"]);
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
  await h.command("runBuiltin", { ...h.target("builtin"), name: "validate" });
  h.picks.push(() => []);
  await h.command("runBuiltinWithParameters", { ...h.target("builtin"), name: "validate" });
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
  doc.workflows = [{ name: "all", run_options: [], command: ["workflow", "run", "all"] }];
  const h = harness(t, [doc]);
  await h.controller.ready();
  const root = h.controller.provider.getChildren()[0];
  const project = root.children.find(node => node.project);
  for (const owner of [root, project]) {
    const builtins = owner.children.find(node => node.label === "Built-in commands");
    assert.deepEqual(builtins.children.map(node => node.label), ["CLI help", "help", "validate", "workflow", "self-service", "maintainer"]);
    assert.deepEqual(builtins.children.find(node => node.label === "workflow").children.map(node => node.label), ["list", "show"]);
  }
  for (const label of ["Jobs", "Workflows"]) {
    const node = project.children.find(node => node.label === label).children[0];
    assert.equal(node.contextValue, `${node.kind}-report`);
  }
  assert.equal(root.children[0].children[0].contextValue, "workflow-report");
  // Removing the duplicate rows does not remove CLI operations or saved tasks.
  await h.command("runBuiltin", { ...h.target("builtin"), name: "workflow run" });
  assert.equal(h.tasks[0].execution.args.at(-1), "run");
});

test("report actions target job variants and aggregate workflows without running or prompting", async t => {
  const doc = inventory();
  doc.ci = true;
  doc.mode = "workspace";
  doc.commands = builtinCommands();
  doc.workflows = [{ name: "all", run_options: [], command: ["workflow", "run", "all"] }];
  doc.projects[0].jobs[0].params[0].required = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  h.picks.push(items => items.filter(item => item.name === "large"));
  await h.command("selectVariant", h.target());
  h.api.window.showQuickPick = h.api.window.showInputBox = () => assert.fail("Report actions must not prompt for run parameters");
  await h.command("openReport", h.target());
  await h.command("openReport", h.target("workflow"));
  await h.command("openReport", { kind: "workflow", name: "all", root: doc.root });
  assert.deepEqual(h.tasks[0].execution.args, ["--variant", "large", "report", "open", "--if-exists", "--", "build"]);
  assert.deepEqual(h.tasks[1].execution.args, ["report", "open", "--if-exists", "--workflow", "build"]);
  assert.deepEqual(h.tasks[2].execution.args, ["report", "open", "--if-exists", "--workflow", "all"]);
  for (const task of h.tasks) {
    assert.equal(task.definition.report, true);
    assert.deepEqual((await h.api.taskProvider.resolveTask(task)).execution.args, task.execution.args);
  }
  assert.deepEqual(h.errors, []);
  const stale = h.target("workflow");
  doc.projects[0].commands.find(spec => spec.name === "report").children = [];
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
  assert.deepEqual(h.tasks[0].execution.args, ["build", "--help"]);
  assert.deepEqual(h.tasks[1].execution.args, ["workflow", "run", "build", "--help"]);
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
  const setup = builtins.children.find(node => node.label === "self-service");
  const creds = setup.children.find(node => node.label === "creds");
  assert.equal(h.controller.provider.getTreeItem(setup).state, h.api.TreeItemCollapsibleState.Collapsed);
  assert.equal(creds.contextValue, "builtin-group");
  assert.deepEqual(creds.children.map(node => node.label), ["list", "set"]);
  const help = builtins.children.find(node => node.label === "CLI help");
  assert.doesNotThrow(() => JSON.stringify(help.command));
  await h.command("showHelp", help.command.arguments[0]);
  await h.command("showHelp", creds);
  assert.deepEqual(h.tasks[0].execution.args, ["--help"]);
  assert.deepEqual(h.tasks[1].execution.args, ["self-service", "creds", "--help"]);
});

test("built-in required input cancellation prevents execution; secret entry stays in the terminal", async t => {
  const h = harness(t);
  await h.controller.ready();
  const target = { ...h.target("builtin"), name: "self-service creds set" };
  await h.command("runBuiltin", target);
  assert.equal(h.tasks.length, 0);
  h.inputs.push("service name");
  await h.command("runBuiltin", target);
  assert.deepEqual(h.tasks[0].execution.args, ["self-service", "creds", "set", "--", "service name"]);
  assert.deepEqual(h.tasks[0].definition.inputs, { name: ["service name"] });
  assert.equal(h.tasks[0].presentationOptions.focus, true);
  assert.deepEqual((await h.api.taskProvider.resolveTask(h.tasks[0])).execution.args, h.tasks[0].execution.args);
  assert.equal((await h.api.taskProvider.provideTasks()).some(task => task.definition.kind === "builtin"), false);
});

test("built-in option prompts preserve choices and positional values", async t => {
  const h = harness(t);
  await h.controller.ready();
  h.picks.push(items => items, items => items.find(item => item.value === "json"));
  h.inputs.push("project.name");
  await h.command("runBuiltinWithParameters", { ...h.target("builtin"), name: "maintainer config show" });
  assert.deepEqual(h.tasks[0].execution.args, ["maintainer", "config", "show", "--format=json", "--", "project.name"]);
  assert.deepEqual(h.errors, []);
});

test("built-in execution rechecks workspace trust and refreshed command permissions", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  const target = { ...h.target("builtin"), name: "self-service creds list" };
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

test("VMR root built-ins omit member configuration and member help selects its repository", async t => {
  const doc = inventory();
  doc.mode = "workspace";
  doc.commands = builtinCommands();
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("runBuiltin", { kind: "builtin", root: doc.root, name: "self-service creds list" });
  assert.deepEqual(h.tasks[0].execution.args, ["self-service", "creds", "list"]);
  const project = h.controller.provider.getChildren()[0].children[0];
  const commands = project.children.find(node => node.label === "Built-in commands").children;
  await h.command("showHelp", commands[0]);
  assert.deepEqual(h.tasks[1].execution.args, ["--help"]);
});

test("clean bypasses required parameters and survives saved-task restoration", async t => {
  const doc = inventory();
  doc.projects[0].jobs[0].params[0].required = true;
  const h = harness(t, [doc]);
  await h.controller.ready();
  await h.command("clean", h.target());
  assert.equal(h.tasks.length, 1);
  assert.equal(h.tasks[0].definition.clean, true);
  assert.deepEqual(h.tasks[0].execution.args, ["--variant", "small", "--clean", "run", "build"]);
  const restored = await h.api.taskProvider.resolveTask(h.tasks[0]);
  assert.deepEqual(restored.execution.args, h.tasks[0].execution.args);
  await h.command("reRun", h.target("workflow"));
  assert.equal(h.tasks[1].definition.reRun, true);
  assert.deepEqual(h.tasks[1].execution.args, ["--variant", "small", "--re-run", "workflow", "run", "build"]);
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
  assert.ok(h.tasks[0].execution.args.includes("--dry-run"));
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
  assert.deepEqual(h.tasks[0].execution.args.slice(-1), ["validate"]);
  assert.equal(h.tasks[0].execution.options.cwd, h.target().project.invocation.cwd);
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
  h.picks.push(items => items.filter(item => item.name === "large"));
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
  assert.deepEqual(h.tasks[0].execution.args, ["init", "--config-dir", "configuration", "--", doc.root]);
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


test("variant selection uses only the per-target setting", async t => {
  const h = harness(t);
  h.state.set(`variant:${h.target().project.entry_file}`, "large");
  await h.controller.ready();
  await h.command("run", h.target());
  assert.deepEqual(h.tasks[0].execution.args, ["--variant", "small", "run", "build"]);
});

test("configuration list entries use names and values and skip named-step wrappers", async t => {
  const doc = inventory();
  doc.projects[0].configuration.value = {
    jobs: { build: { steps: [{ compile: { run: "make" } }, { test: { uses: "echo" } }, { run: "echo direct", name: "Direct step" }] } },
    environment: { keep: ["PATH", "HOME", "PATH"] },
    artifactory: { events: { push: { path: "branches" } } },
  };
  const h = harness(t, [doc]);
  await h.controller.ready();
  const config = h.controller.provider.getChildren()[0].children[0].children.find(node => node.label === "Configuration");
  const jobs = config.children.find(node => node.label === "jobs");
  const steps = jobs.children[0].children[0];
  assert.deepEqual(steps.children.map(node => node.label), ["compile", "test", "Direct step"]);
  assert.deepEqual(steps.children[0].configPath, ["jobs", "build", "steps", 0, "compile"]);
  assert.deepEqual(steps.children[0].children.map(node => node.label), ["run"]);
  assert.equal(steps.children[0].icon, "terminal");
  assert.equal(jobs.icon, "tasklist");
  const keep = config.children.find(node => node.label === "environment").children[0];
  assert.deepEqual(keep.children.map(node => node.label), ["PATH", "HOME", "PATH"]);
  assert.equal(new Set(keep.children.map(node => node.id)).size, 3);
  assert.ok(keep.children.every(node => !node.icon && !node.description));
  await h.command("openConfig", steps.children[0]);
  assert.deepEqual(h.opened.at(-1).path, ["jobs", "build", "steps", 0, "compile"]);
});

test("unchanged refreshes and edit preflight do not redraw the tree; identities survive saves", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  const before = h.treeChanges();
  const ids = tree => tree.flatMap(node => [node.id, ...ids(node.children || [])]);
  const original = ids(h.controller.provider.getChildren());
  await h.controller.refresh();
  assert.equal(h.treeChanges(), before);
  doc.projects[0].configuration.value.jobs.build.help = "New help";
  await h.editorActions.project(doc.projects[0].entry_file, { publish: false });
  assert.equal(h.treeChanges(), before);
  assert.deepEqual(ids(h.controller.provider.getChildren()), original);
  await h.editorActions.project(doc.projects[0].entry_file);
  assert.equal(h.treeChanges(), before + 1);
  assert.deepEqual(ids(h.controller.provider.getChildren()), original);
});

test("an editor save waits for a superseding refresh instead of acknowledging an old snapshot", async t => {
  const doc = inventory();
  const h = harness(t, [doc]);
  await h.controller.ready();
  let started, releaseFirst, releaseLatest, latestStarted;
  const firstStarted = new Promise(resolve => { started = resolve; });
  const nextStarted = new Promise(resolve => { latestStarted = resolve; });
  let reads = 0;
  t.mock.method(core, "readInventory", async () => {
    if (++reads === 1) { started(); await new Promise(resolve => { releaseFirst = resolve; }); }
    else { latestStarted(); await new Promise(resolve => { releaseLatest = resolve; }); }
    return structuredClone(doc);
  });
  const saved = h.editorActions.project(doc.projects[0].entry_file);
  await firstStarted;
  doc.projects[0].configuration.value.jobs.added = { steps: [{ hello: { run: "echo hello" } }] };
  const watcherRefresh = h.controller.refresh();
  releaseFirst();
  await nextStarted;
  releaseLatest();
  const [owner] = await Promise.all([saved, watcherRefresh]);
  assert.deepEqual(owner.project.configuration.value.jobs.added, doc.projects[0].configuration.value.jobs.added);
});

test("tree icons use distinct theme colours for jobs, workflows and configuration categories", async t => {
  const h = harness(t);
  await h.controller.ready();
  const project = h.controller.provider.getChildren()[0].children[0];
  const jobs = project.children.find(item => item.label === "Jobs");
  const workflows = project.children.find(item => item.label === "Workflows");
  const config = project.children.find(item => item.label === "Configuration");
  const items = [project, jobs, jobs.children[0], workflows, config].map(item => h.controller.provider.getTreeItem(item));
  assert.deepEqual(items.map(item => item.iconPath.color.id), ["charts.blue", "charts.green", "charts.green", "charts.purple", "charts.yellow"]);
});

test("job run form selects multiple variants and restores the same step range", async t => {
  const doc = inventory();
  doc.projects[0].jobs[0].run_options = [builtinParam("start", { kind: "option", option: "--from", choices: ["compile"] })];
  const h = harness(t, [doc]); await h.controller.ready();
  h.forms.push(() => ({ params: {}, preview: true, variants: ["small", "large"], runOptions: { start: ["compile"] } }));
  await h.command("runWithParameters", h.target());
  assert.equal(h.tasks.length, 2);
  for (const task of h.tasks) {
    assert.deepEqual(task.definition.runOptions, { start: ["compile"] });
    assert.ok(task.execution.args.includes("--from=compile"));
    assert.deepEqual((await h.api.taskProvider.resolveTask(task)).execution.args, task.execution.args);
  }
  assert.deepEqual(h.errors, []);
});

test("workflow gear opens owner variant choices and preserves dry run", async t => {
  const h = harness(t); await h.controller.ready();
  h.forms.push((target) => {
    assert.equal(target.kind, "workflow");
    return { params: {}, preview: true, variants: ["large"], runOptions: {} };
  });
  await h.command("runWithParameters", h.target("workflow"));
  assert.equal(h.tasks.length, 1);
  assert.deepEqual(h.tasks[0].execution.args, ["--variant", "large", "workflow", "run", "build", "--dry-run"]);
  assert.deepEqual(h.errors, []);
});

test("a step removed while the run form is open prevents the entire variant batch", async t => {
  const doc = inventory();
  const option = builtinParam("start", { kind: "option", option: "--from", choices: ["configure", "compile"] });
  doc.projects[0].jobs[0].run_options = [option];
  const h = harness(t, [doc]); await h.controller.ready();
  h.forms.push(async () => {
    option.choices = ["configure"];
    await h.controller.refresh();
    return { params: {}, preview: false, variants: ["small", "large"], runOptions: { start: ["compile"] } };
  });
  await h.command("runWithParameters", h.target());
  assert.equal(h.tasks.length, 0);
  assert.match(h.errors[0], /available value/);
});
