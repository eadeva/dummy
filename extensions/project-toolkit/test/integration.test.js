"use strict";

// A real Node -> Python CLI contract test; controller tests use an injected API.
// Set PTK_TEST_PYTHON to the interpreter with this checkout's dependencies.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const core = require("../src/core");

const python = process.env.PTK_TEST_PYTHON;
const repo = path.resolve(__dirname, "../../..");
const env = { ...process.env, PYTHONPATH: path.join(repo, "src"), PTK_CI: "0", PTK_ROLE: "user", NO_COLOR: "1" };

function invoke(cwd, args) {
  const result = spawnSync(python, ["-m", "ptk", ...args], { cwd, env, encoding: "utf8", timeout: 30000 });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  return result.stdout;
}

function writeProject(root, config) {
  const documents = {
    ".main.ptk.yml": { repository: config.repository },
    "project.ptk.yml": config.project,
    "project.variants.ptk.yml": { default: config.variants?.default },
  };
  for (const [group, values] of Object.entries({ jobs: config.jobs, workflows: config.workflows, variants: config.variants?.variants })) {
    for (const [name, value] of Object.entries(values || {})) documents[`${group}/${name}.ptk.yml`] = value;
  }
  for (const [file, value] of Object.entries(documents)) {
    const target = path.join(root, file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify(value));
  }
}

function project(root, alias) {
  fs.mkdirSync(root, { recursive: true });
  writeProject(root, {
    repository: { alias, config_path: "." }, project: { name: alias, default_job: "build" },
    variants: { default: "small", variants: { small: {}, large: {} } },
    jobs: { build: {
      params: {
        message: { default: "hello" }, verbose: { type: "bool", default: true },
        tags: { type: "list", default: ["one"] }, token: { type: "secret", env: "PTK_TEST_SECRET" },
      },
      steps: [{ say: { uses: "echo", with: { message: "${params.message} ${params.verbose} ${params.tags}" } } }],
    } },
    workflows: { verify: { steps: [{ build: "build" }] } },
  });
}

test("installed PTK supplies the variable catalogue and raw job field capabilities", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk variables "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "demo");
  const config = JSON.parse(invoke(root, ["describe", "--json", "--configuration"])).projects[0].configuration;
  const V = require("../media/variables"), S = require("../media/schema"), E = require("../src/project-edits");
  const file = path.join(root, "jobs/build.ptk.yml");
  const value = JSON.parse(fs.readFileSync(file, "utf8"));
  const state = { value, variables: config.variables, pathBindings: E.bindingsForFile(config, file) };
  const entries = V.available(state, E.schemaForFile(config, file), ["steps", 0, "say", "with", "message"], S);
  assert.ok(entries.some(entry => entry.reference === "git.short_commit"));
  assert.ok(entries.some(entry => entry.reference === "params.message"));
  assert.ok(!entries.some(entry => entry.reference === "params.token"));
  assert.ok(!entries.some(entry => entry.reference.startsWith("github.")));
  assert.deepEqual(V.available(state, E.schemaForFile(config, file), ["steps", 0, "say", "uses"], S), []);
});

test("actual PTK inventory, preview, job parameters and variant inspection agree with extension arguments", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk extension "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "demo");
  const before = fs.readdirSync(root, { recursive: true });
  const doc = core.parseInventory(invoke(root, ["describe", "--json", "--configuration"]));
  const target = core.availableTargets([{ inventory: doc }]).find(target => target.kind === "job");
  assert.match(invoke(root, core.argsFor(target, { variant: "large", report: true })), /Info:.*job.*hasn't run yet/s);
  const workflow = core.availableTargets([{ inventory: doc }]).find(target => target.kind === "workflow");
  assert.match(invoke(root, core.argsFor(workflow, { report: true })), /Info:.*workflow.*hasn't run yet/s);
  assert.equal(target.spec.params.some(p => p.name === "token"), false);
  assert.match(invoke(root, core.argsFor(target, { help: true })), /--message/);
  const builtins = core.availableBuiltins([{ inventory: doc }]);
  const show = builtins.find(target => target.name === "setup config show");
  assert.equal(JSON.parse(invoke(root, core.argsFor(show, { inputs: { path: ["project.name"], fmt: ["json"] } }))), "demo");
  invoke(root, core.argsFor(builtins.find(target => target.name === "setup creds list")));
  invoke(root, core.argsFor(builtins.find(target => target.name === "setup creds set"), { help: true }));
  invoke(root, core.argsFor(builtins.find(target => target.name === "--help"), { help: true }));
  assert.deepEqual(fs.readdirSync(root, { recursive: true }), before);
  const options = { variant: "large", params: { message: "text with spaces;$(literal)", verbose: "false", tags: "one,two" } };
  const preview = invoke(root, core.argsFor(target, { ...options, preview: true }));
  assert.match(preview, /text with spaces/);
  assert.deepEqual(fs.readdirSync(root, { recursive: true }), before);
  const output = invoke(root, core.argsFor(target, options));
  assert.match(output, /text with spaces;\$\(literal\)/);
  const run = JSON.parse(fs.readFileSync(path.join(root, "_logs/large/build/run.json"), "utf8"));
  assert.equal(run.params.verbose, false);
  assert.deepEqual(run.params.tags, ["one", "two"]);
  const variantArgs = core.argsFor({ ...target, kind: "variant", name: "large" });
  assert.equal(JSON.parse(invoke(root, [...variantArgs, "--json"])).name, "large");
  assert.ok(fs.existsSync(path.join(root, "_logs")));
});

test("actual VMR discovery supports member jobs and workspace workflow previews", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk vmr extension "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(path.join(root, "a"), "alpha");
  project(path.join(root, "b"), "beta");
  const entry = path.join(root, "a/.main.ptk.yml");
  fs.unlinkSync(path.join(root, "a/project.variants.ptk.yml"));
  for (const name of ["small", "large"]) fs.unlinkSync(path.join(root, `a/variants/${name}.ptk.yml`));
  fs.writeFileSync(path.join(root, ".main.ptk.yml"), "virtual_monorepo: true\nmembers: [a, b]\n");
  fs.mkdirSync(path.join(root, "workflows"));
  fs.writeFileSync(path.join(root, "workflows/verify.ptk.yml"), "steps:\n- build: {repo: alpha, job: build}\n");
  const doc = core.parseInventory(invoke(root, ["describe", "--json", "--configuration"]));
  assert.equal(doc.mode, "workspace");
  const targets = core.availableTargets([{ inventory: doc }]);
  const builtins = core.availableBuiltins([{ inventory: doc }]);
  const member = builtins.find(target => target.project?.alias === "alpha" && target.name === "setup config show");
  assert.equal(JSON.parse(invoke(root, core.argsFor(member, { inputs: { path: ["project.name"], fmt: ["json"] } }))), "alpha");
  const shared = builtins.find(target => !target.project && target.name === "setup config show");
  const configs = invoke(root, core.argsFor(shared, { inputs: { path: ["project.name"], fmt: ["json"] } }));
  assert.match(configs, /"alpha"/);
  assert.match(configs, /"beta"/);
  const job = targets.find(target => target.kind === "job" && target.project.alias === "alpha");
  invoke(root, core.argsFor(job, { preview: true }));
  const workflow = targets.find(target => target.kind === "workflow" && !target.project);
  assert.equal(core.canOpenReport(workflow), true);
  assert.match(invoke(root, core.argsFor(workflow, { report: true })), /Info:.*workflow.*hasn't run yet/s);
  invoke(root, core.argsFor(workflow, { preview: true }));
  assert.equal(fs.existsSync(path.join(root, "_logs")), false);
});

test("actual cleanup controls remove only the chosen job variant", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk clean extension "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "demo");
  const doc = core.parseInventory(invoke(root, ["describe", "--json", "--configuration"]));
  const target = core.availableTargets([{ inventory: doc }]).find(t => t.kind === "job");
  for (const variant of ["small", "large"]) for (const folder of ["_bin", "_builds", "_logs", "_reports"]) {
    const dir = path.join(root, folder, variant, "build");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "marker"), "keep");
  }
  invoke(root, core.argsFor(target, { variant: "large", clean: true }));
  assert.equal(fs.existsSync(path.join(root, "_bin/large/build")), false);
  assert.equal(fs.existsSync(path.join(root, "_bin/small/build/marker")), true);
  const builtins = core.availableBuiltins([{ inventory: doc }]);
  const cleanAll = builtins.find(t => t.name === "clean-all");
  assert.ok(cleanAll);
  invoke(root, core.argsFor(cleanAll, { inputs: { dry_run: ["true"] } }));
  assert.equal(fs.existsSync(path.join(root, "_bin/small/build/marker")), true);
  invoke(root, core.argsFor(cleanAll, { inputs: { yes: ["true"] } }));
  assert.equal(fs.existsSync(path.join(root, "_bin")), false);
});

test("real uv discovery and version-check launch do not sync or alter installed metadata", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, async t => {
  const uv = "uv";
  const version = spawnSync(uv, ["--version"], { encoding: "utf8", timeout: 10000 });
  if (version.error?.code === "ENOENT") { t.skip("uv is not installed"); return; }
  assert.equal(version.status, 0, version.stderr);
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk uv launch "));
  const venv = path.join(root, ".venv");
  const previous = process.env.UV_PROJECT_ENVIRONMENT;
  process.env.UV_PROJECT_ENVIRONMENT = venv;
  t.after(() => {
    if (previous === undefined) delete process.env.UV_PROJECT_ENVIRONMENT;
    else process.env.UV_PROJECT_ENVIRONMENT = previous;
    fs.rmSync(root, { recursive: true, force: true });
  });
  const created = spawnSync(uv, ["venv", "--python", python, venv], { encoding: "utf8", timeout: 30000 });
  assert.equal(created.status, 0, created.stderr);
  const interpreter = path.join(venv, process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const site = spawnSync(interpreter, ["-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], { encoding: "utf8", timeout: 10000 }).stdout.trim();
  const metadata = path.join(site, "ptk_launch_canary-1.0.dist-info", "METADATA");
  fs.mkdirSync(path.dirname(metadata), { recursive: true });
  fs.writeFileSync(metadata, "Metadata-Version: 2.1\nName: ptk-launch-canary\nVersion: 1.0\n");
  const before = fs.readFileSync(metadata, "utf8"); // Deliberately has no RECORD, like the reported damaged environment.
  fs.writeFileSync(path.join(root, "pyproject.toml"), '[project]\nname = "ptk-launch-fixture"\nversion = "1.0"\nrequires-python = ">=3.12"\ndependencies = ["ptk-never-install-this-fixture==0.0.0"]\n[tool.uv]\npackage = false\n');
  const unsafelySynced = spawnSync(uv, ["run", "--offline", "--project", root, "python", "-c", "print('command started')"],
    { cwd: root, env: { ...process.env, UV_NO_SYNC: "0" }, encoding: "utf8", timeout: 30000 });
  assert.notEqual(unsafelySynced.status, 0);
  assert.doesNotMatch(unsafelySynced.stdout, /command started/);
  const doc = require("./fixtures").inventory(root);
  const script = `import json,sys; print(json.dumps(json.loads(${JSON.stringify(JSON.stringify(doc))})) if sys.argv[-3:] == ['describe', '--json', '--configuration'] else 'Version sources and resolved names are valid.')`;
  const settings = { executable: uv, arguments: ["run", "--offline", "--project", root, "python", "-c", script, "--"], timeout: 10 };
  assert.deepEqual(await core.readInventory(settings, root), doc);
  const checked = spawnSync(uv, core.launchArgs(settings, ["version", "check"]), { cwd: root, encoding: "utf8", timeout: 10000 });
  assert.equal(checked.status, 0, checked.stderr);
  assert.match(checked.stdout, /Version sources and resolved names are valid/);
  assert.doesNotMatch(checked.stderr, /Uninstalled|Installed|RECORD/);
  assert.equal(fs.readFileSync(metadata, "utf8"), before);
  assert.equal(fs.existsSync(path.join(root, "uv.lock")), false);
});


test("configuration form round-trips PTK YAML scalar types and creates valid jobs", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const model = require("../src/config-model");
  const S = require("../media/schema");
  const schema = require("../media/config-schema.json");
  const source = "a: on\nb: off\nc: y\nd: n\ne: 008\nf: 1e3\ng: 1.2e3\nh: -.5\ni: 01:02\nj: 1.0e+20\nk: 1.0e-10\nl: 9007199254740993\nm: 2024-01-01\n";
  const result = model.edit(source, [
    { op: "add", path: ["text"], value: "on" },
    { op: "add", path: ["tiny"], value: 0.0000001 },
  ]);
  const check = spawnSync(python, ["-c", "import json,sys,yaml; a,b=json.load(sys.stdin); before=yaml.safe_load(a); after=yaml.safe_load(b); assert after.pop('text') == 'on'; assert after.pop('tiny') == 0.0000001; assert before == after, (before,after); assert {k:type(v) for k,v in before.items()} == {k:type(v) for k,v in after.items()}"], { input: JSON.stringify([source, result]), encoding: "utf8" });
  assert.equal(check.status, 0, check.stderr);
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk config form "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "form");
  const entry = path.join(root, ".main.ptk.yml");
  const config = core.parseInventory(invoke(root, ["describe", "--json", "--configuration"])).projects[0].configuration;
  const docs = new Map(config.files.map(file => [file, fs.readFileSync(file, "utf8")]));
  const changes = require("../src/project-edits").plan(config, docs, [{ op: "add", path: ["jobs", "new-job"], value: S.initial(schema.$defs.JobSpec, schema) }]);
  for (const [file, text] of changes) fs.writeFileSync(file, text);
  invoke(root, ["setup", "config", "validate"]);
  assert.ok(core.parseInventory(invoke(root, ["describe", "--json", "--configuration"])).projects[0].jobs.some(job => job.name === "new-job"));
});

test("runtime schema routes events to their fixed owning file", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const { plan } = require("../src/project-edits");
  const S = require("../media/schema");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk composed form "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "composed");
  fs.writeFileSync(path.join(root, "artifactory_paths.ptk.yml"), "url: https://example.invalid\nrepository: packages\nevents:\n  push: {path: branches}\n");
  const read = () => core.parseInventory(invoke(root, ["describe", "--json", "--configuration"])).projects[0].configuration;
  let config = read();
  const event = S.initial(config.schema.$defs.EventRoute, config.schema);
  assert.deepEqual(event, { path: "" });
  function apply(operations) {
    const docs = new Map(config.files.map(file => [file, fs.readFileSync(file, "utf8")]));
    for (const [file, text] of plan(config, docs, operations)) fs.writeFileSync(file, text);
    invoke(root, ["setup", "config", "validate"]);
    config = read();
  }
  apply([{ op: "add", path: ["artifactory", "events", "release"], value: event }]);
  apply([{ op: "set", path: ["artifactory", "events", "push", "path"], value: "new-branches" }]);
  assert.equal(config.value.artifactory.events.push.path, "new-branches");
  assert.deepEqual(config.value.artifactory.events.release, { path: "" });
  assert.equal(config.sources.find(source => JSON.stringify(source.path) === JSON.stringify(["artifactory", "events", "push", "path"])).file, path.join(root, "artifactory_paths.ptk.yml"));
});

test("project form saves to the owning file then detects stale sources", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, async t => {
  const { createEditors } = require("../src/editors");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk live form "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "live");
  const entry = path.join(root, ".main.ptk.yml");
  const describe = () => ({ root, project: core.parseInventory(invoke(root, ["describe", "--json", "--configuration"])).projects[0] });
  const documents = new Map(), messages = [];
  let receive;
  const uri = fsPath => ({ fsPath, toString() { return fsPath; } });
  const disposable = () => ({ dispose() {} });
  async function document(uri) {
    if (!documents.has(uri.fsPath)) {
      let text = fs.readFileSync(uri.fsPath, "utf8");
      const doc = { uri, version: 1, isDirty: false, getText: () => text, positionAt: offset => offset,
        replace(start, end, next) { text = text.slice(0, start) + next + text.slice(end); this.version++; this.isDirty = true; },
        async save() { fs.writeFileSync(uri.fsPath, text); this.isDirty = false; return true; },
      };
      documents.set(uri.fsPath, doc);
    }
    return documents.get(uri.fsPath);
  }
  const panel = { webview: { cspSource: "test:", asWebviewUri: uri => uri.fsPath,
    postMessage: async message => { messages.push(message); return true; },
    onDidReceiveMessage: handler => { receive = handler; return disposable(); } }, onDidDispose: disposable, dispose() {}, reveal() {} };
  const api = {
    Uri: { file: uri, joinPath: (base, ...parts) => uri(path.join(base.fsPath, ...parts)) }, ViewColumn: { Active: 1 },
    Range: class { constructor(start, end) { Object.assign(this, { start, end }); } },
    Position: class { constructor(line, character) { Object.assign(this, { line, character }); } },
    WorkspaceEdit: class { changes = []; replace(uri, range, text) { this.changes.push({ uri, range, text }); } createFile(uri) { this.changes.push({ uri, create: true }); } insert(uri, position, text) { this.replace(uri, { start: 0, end: 0 }, text); } },
    workspace: { isTrusted: true, openTextDocument: document,
      fs: { createDirectory: async uri => fs.mkdirSync(uri.fsPath, { recursive: true }) },
      async applyEdit(edit) { for (const change of edit.changes) {
        if (change.create) fs.writeFileSync(change.uri.fsPath, "", { flag: "wx" });
        else (await document(change.uri)).replace(change.range.start, change.range.end, change.text);
      } return true; },
    },
    window: { registerCustomEditorProvider: disposable, createWebviewPanel: () => panel,
      showInputBox: async () => "config/parameters.ptk.yml", showErrorMessage: async error => assert.fail(error) },
  };
  const editors = createEditors(api, { subscriptions: [], extensionUri: uri(path.join(repo, "extensions/project-toolkit")) }, { project: async () => describe() });
  await editors.openProject(describe(), ["jobs", "build", "params"]);
  await receive({ type: "ready" });
  await receive({ type: "edit", id: 1, version: messages.at(-1).version,
    operations: [{ op: "set", path: ["jobs", "build", "params", "message", "default"], value: "updated" }] });
  assert.equal(messages.at(-1).issue, undefined);
  assert.equal(messages.at(-1).value.jobs.build.params.message.default, "updated");
  assert.ok(fs.existsSync(path.join(root, "jobs/build.ptk.yml")));
  assert.equal(fs.existsSync(path.join(root, "config/parameters.ptk.yml")), false);
  invoke(root, ["setup", "config", "validate"]);
  fs.appendFileSync(entry, "\n# external change\n");
  await receive({ type: "edit", id: 2, version: messages.at(-1).version,
    operations: [{ op: "set", path: ["jobs", "build", "params", "message", "default"], value: "should not apply" }] });
  assert.match(messages.at(-1).issue, /source file changed/i);
  assert.equal(describe().project.configuration.value.jobs.build.params.message.default, "updated");
});

test("registered component edits create a local document and entity renames round-trip", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const { plan } = require("../src/project-edits");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk component form "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "components");
  const read = () => core.parseInventory(invoke(root, ["describe", "--json", "--configuration"])).projects[0].configuration;
  let config = read();
  function apply(operations) {
    const docs = new Map(config.files.map(file => [file, fs.readFileSync(file, "utf8")]));
    for (const [file, text] of plan(config, docs, operations)) {
      if (text === null) fs.unlinkSync(file);
      else { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, text); }
    }
    invoke(root, ["setup", "config", "validate"]);
    config = read();
  }
  apply([{ op: "add", path: ["project", "components"], value: { networking: { path: "src/networking" } } }]);
  apply([{ op: "add", path: ["variants", "components", "networking", "features"], value: { TLS: { type: "bool", default: true } } }]);
  assert.ok(fs.existsSync(path.join(root, "src/networking/component.variants.ptk.yml")));
  assert.equal(config.value.variants.components.networking.features.TLS.default, true);
  apply([{ op: "add", path: ["jobs", "check"], value: { steps: [{ inspect: { uses: "echo" } }] } }]);
  apply([{ op: "rename", path: ["jobs", "check"], name: "inspect" }]);
  assert.equal(fs.existsSync(path.join(root, "jobs/check.ptk.yml")), false);
  assert.ok(fs.existsSync(path.join(root, "jobs/inspect.ptk.yml")));
  apply([{ op: "remove", path: ["jobs", "inspect"] }]);
  assert.equal(fs.existsSync(path.join(root, "jobs/inspect.ptk.yml")), false);
});

test("new configuration items from the installed schema validate with their required descendants", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const S = require("../media/schema"), { plan } = require("../src/project-edits");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk required fields "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "required");
  const read = () => core.parseInventory(invoke(root, ["describe", "--json", "--configuration"])).projects[0].configuration;
  let config = read();
  function add(field, definition, existing = []) {
    const value = S.initial(config.schema.$defs[definition], config.schema, { configuration: config.value, existing });
    const docs = new Map(config.files.map(file => [file, fs.readFileSync(file, "utf8")]));
    for (const [file, text] of plan(config, docs, [{ op: "add", path: field, value }])) {
      fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, text);
    }
    invoke(root, ["setup", "config", "validate"]);
    config = read();
    assert.equal(config.error, null);
    return value;
  }
  add(["artifactory"], "ArtifactoryStructure");
  assert.deepEqual(config.value.artifactory.events, { push: { path: "" } });
  add(["versioning"], "VersioningSpec");
  add(["jobs", "new-job"], "JobSpec");
  add(["jobs", "new-job", "steps", 1], "StepEntry", config.value.jobs["new-job"].steps);
  assert.deepEqual(config.value.jobs["new-job"].steps.map(item => Object.keys(item)[0]), ["step", "step_2"]);
  add(["jobs", "new-job", "steps", 0, "step", "python"], "PythonSpec");
  add(["workflows", "new-workflow"], "WorkflowSpec");
  assert.equal(config.value.workflows["new-workflow"].steps[0].job.job, "build");
});
