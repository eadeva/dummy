"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../media/schema"), C = require("../media/creation"), D = require("../media/dependencies");
const schema = require("../media/config-schema.json");

test("every schema-owned creation mode yields an independent ordinary configuration draft", () => {
  for (const definition of ["StepSpec", "JobSpec", "PythonSpec"]) {
    const spec = schema.$defs[definition];
    for (const mode of S.stepModes(spec, schema)) {
      const draft = S.stepInitial(spec, schema, mode.id);
      assert.deepEqual(C.problems(S, spec, schema, draft), [], `${definition}: ${mode.id}`);
      draft.changed = true;
      assert.equal(S.stepInitial(spec, schema, mode.id).changed, undefined);
      assert.equal(mode.initial.changed, undefined);
      assert.equal(Object.hasOwn(mode.initial, "mode"), false);
    }
  }
  assert.throws(() => S.stepInitial(schema.$defs.StepSpec, schema, ""), /Choose a step mode/);
  assert.throws(() => S.stepModes({}, schema), /Update PTK/);
});

test("wizard field checks catch missing values, ranges, forbidden names and duplicate additions", () => {
  assert.match(C.problems(S, schema.$defs.ProjectSpec, schema, {})[0], /name.*required/);
  assert.match(C.problems(S, schema.$defs.StepSpec, schema, {run: ["tool"], timeout: -1})[0], /greater than/);
  assert.match(C.problems(S, schema.$defs.StepSpec, schema, {run: ["tool"], unexpected: true})[0], /unknown field/);
  assert.match(C.problems(S, {type: "integer"}, schema, 1.2)[0], /expected integer/);
  assert.equal(C.fieldName([], "ignored", {}), 0);
  assert.throws(() => C.fieldName({build: {}}, "build", {}), /already exists/);
  assert.throws(() => C.fieldName({}, "__proto__", {}), /valid name/);
  assert.throws(() => C.fieldName({}, "Build Job", schema.properties.jobs), /lowercase/);
  assert.throws(() => C.fieldName({}, "maintainer", schema.properties.jobs), /reserved/);
  assert.throws(() => C.fieldName({}, "unknown", {additionalProperties: false, properties: {name: {}}}), /available field/);
});

test("graph summaries distinguish declared execution forms without resolving secrets", () => {
  assert.equal(D.describe({run: ["check.py"], python: {project: "."}}).label, "Python project");
  assert.equal(D.describe({run: ["check.py"]}).label, "Python script");
  assert.equal(D.describe({uses: "echo"}).kind, "builtin");
  assert.equal(D.describe({generators: ["cmake"]}).command, "cmake");
  assert.equal(D.describe({job: "repo:build"}).command, "repo:build");
  assert.equal(D.describe({run: ["tool", "two words"], secrets: {TOKEN: "vault.token"}}).command, 'tool "two words"');
  assert.equal(D.describe({run: [7], generators: "invalid"}).command, "7");
});

test("graph highlights complete dependency paths across branches and joins", () => {
  const entries = D.nodes({root: {run: "r"}, left: {run: "l", needs: "root"}, right: {run: "r", needs: "root"}, join: {run: "j", needs: ["left", "right"]}, independent: {run: "i"}});
  const family = D.related(entries, "left");
  assert.deepEqual([...family.ancestors], ["root"]);
  assert.deepEqual([...family.descendants], ["join"]);
  assert.deepEqual(D.related(entries, "missing"), {ancestors: new Set(), descendants: new Set()});
});

function setup(t, spec = schema.properties.jobs, parent = {}, extra = {}) {
  const dom = require("./creation-dom"), previous = global.document;
  global.document = dom.document(); t.after(() => { global.document = previous; });
  const container = new dom.Element("div"), writes = [], cancellations = [];
  const api = C.mount(container, {
    S, schema, spec, parent, path: ["jobs"], configuration: {jobs: {build: {steps: {check: {run: "check"}}}}},
    input: (value, field, change, id) => {
      const input = new dom.Element("input"); input.setAttribute("id", id); input.value = String(value);
      input.addEventListener("input", () => change(input.value)); return input;
    },
    onCreate: (key, value) => writes.push({key, value}), onCancel: () => cancellations.push(true), ...extra,
  });
  const all = () => container.all();
  const byId = id => all().find(node => node.attributes.id === id);
  const click = name => { const button = all().find(node => node.tagName === "BUTTON" && node.textContent === name); assert.ok(button, name); button.emit("click"); };
  const fill = (id, value, event = "input") => { const node = byId(id); assert.ok(node, id); node.value = value; node.emit(event); };
  return {api, writes, cancellations, all, byId, click, fill};
}

test("setup holds edits through back/review and only creates after the final action", t => {
  const h = setup(t);
  h.fill("creation-name", "verify");
  h.click("Configure"); assert.equal(h.writes.length, 0);
  assert(h.all().some(node => /Choose a step mode/.test(node.textContent)));
  h.fill("creation-mode", "python-editable", "change"); h.click("Configure");
  h.fill('create-value-["steps","step","python","project"]', "tools/dev-check");
  h.click("Back"); h.click("Configure");
  assert.equal(h.byId('create-value-["steps","step","python","project"]').value, "tools/dev-check");
  h.click("Review"); assert.equal(h.writes.length, 0);
  h.click("Create");
  assert.equal(h.writes.length, 1);
  assert.equal(h.writes[0].value.steps.step.python.project, "tools/dev-check");
  assert.equal(h.writes[0].key, "verify");
});

test("cancel and mode replacement do not leak draft writes", t => {
  const h = setup(t, schema.$defs.JobSpec.properties.steps);
  h.fill("creation-name", "compile"); h.fill("creation-mode", "python-project", "change"); h.click("Configure");
  h.fill('create-value-["python","project"]', "local");
  h.click("Back"); h.fill("creation-mode", "builtin", "change"); h.click("Configure"); h.click("Review");
  assert(h.all().some(node => node.tagName === "PRE" && node.textContent.includes('"uses": "echo"') && !node.textContent.includes('"python"')));
  h.click("Cancel setup"); assert.equal(h.cancellations.length, 1); assert.equal(h.writes.length, 0);
});

test("arbitrary fields use the same setup flow and preserve rejection drafts", t => {
  let reject = true;
  const h = setup(t, {type: "object", additionalProperties: {}}, {}, {onCreate() { if (reject) throw new Error("Source changed"); }});
  h.fill("creation-name", "target"); h.fill("creation-type", "string", "change"); h.click("Configure");
  h.fill("create-value-[]", "chosen"); h.click("Review"); h.click("Create");
  assert(h.all().some(node => node.textContent === "Source changed"));
  h.click("Back"); assert.equal(h.byId("create-value-[]").value, "chosen");
  reject = false; h.click("Review"); h.api.setBusy(true);
  assert(h.all().filter(node => ["BUTTON", "INPUT", "SELECT"].includes(node.tagName)).every(node => node.disabled));
  h.api.issue("Try again"); assert(h.all().some(node => node.tagName === "BUTTON" && !node.disabled));
});

test("list item setup appends a configured value without mutating the original list", t => {
  const parent = ["existing"];
  const h = setup(t, {type: "array", items: {type: "string", minLength: 1}}, parent);
  h.click("Configure"); h.fill("create-value-[]", "new item"); h.click("Review"); h.click("Create");
  assert.deepEqual(h.writes, [{key: 1, value: "new item"}]);
  assert.deepEqual(parent, ["existing"]);
});

test("graph-dependent defaults and unused workflow targets reach review", t => {
  const h = setup(t, schema.$defs.WorkflowSpec.properties.jobs, {build: {job: "build"}}, {defaults: {needs: ["build"]}, jobChoices: ["test"]});
  h.fill("creation-name", "checks"); h.click("Configure"); h.click("Review"); h.click("Create");
  assert.deepEqual(h.writes[0], {key: "checks", value: {job: "test", needs: ["build"]}});
});

test("adding a nested step inside job setup also requires an explicit mode", t => {
  const h = setup(t);
  h.fill("creation-name", "verify"); h.fill("creation-mode", "builtin", "change"); h.click("Configure");
  const name = () => h.all().find(node => node.attributes["aria-label"] === "New field in steps");
  name().value = "second"; name().emit("input"); h.click("Add field to steps");
  assert(h.all().some(node => /Choose a step mode/.test(node.textContent)));
  name().value = "second"; name().emit("input");
  const mode = h.all().find(node => node.attributes["aria-label"] === "Mode for new entry in steps");
  mode.value = "python-venv"; mode.emit("change"); h.click("Add field to steps");
  h.click("Review"); h.click("Create");
  assert.deepEqual(h.writes[0].value.steps.second.python, {venv: {requirements: [], packages: []}});
});
