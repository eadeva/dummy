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

function project(root, alias) {
  fs.mkdirSync(root, { recursive: true });
  fs.writeFileSync(path.join(root, ".main.ptk.yml"), JSON.stringify({
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
  }));
}

test("actual PTK inventory, preview, job parameters and variant inspection agree with extension arguments", { skip: !python && "Set PTK_TEST_PYTHON to run CLI integration" }, t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk extension "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  project(root, "demo");
  const before = fs.readdirSync(root, { recursive: true });
  const doc = core.parseInventory(invoke(root, ["describe", "--json"]));
  const target = core.availableTargets([{ inventory: doc }]).find(target => target.kind === "job");
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
  fs.writeFileSync(path.join(root, ".main.ptk.yml"), "virtual_monorepo: true\nmembers: [a, b]\n");
  fs.writeFileSync(path.join(root, "workflow.ptk.yml"), "workflows:\n  verify:\n    steps:\n    - build: {repo: alpha, job: build}\n");
  const doc = core.parseInventory(invoke(root, ["describe", "--json"]));
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
  invoke(root, core.argsFor(job, { preview: true, variant: "large" }));
  const workflow = targets.find(target => target.kind === "workflow" && !target.project);
  invoke(root, core.argsFor(workflow, { preview: true }));
  assert.equal(fs.existsSync(path.join(root, "_logs")), false);
});
