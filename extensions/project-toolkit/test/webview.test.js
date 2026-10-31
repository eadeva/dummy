"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("node:path");
let chromium;
try { ({ chromium } = require(process.env.PTK_TEST_PLAYWRIGHT || "playwright")); } catch {}
const options = { skip: !chromium && "Install Playwright or set PTK_TEST_PLAYWRIGHT for real webview tests" };
const media = path.resolve(__dirname, "../media");
const schema = require("../media/config-schema.json");
const variables = require("./variable-fixtures");

async function form(t, value = { vars: { first: "original", second: "other", unused: "remove me" } }, selection = ["vars"]) {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
  page.on("pageerror", error => assert.fail(error.message));
  await page.setContent('<!doctype html><html><body><div id="app"></div></body></html>');
  await page.evaluate(() => {
    window.messages = [];
    window.acquireVsCodeApi = () => ({ getState: () => ({}), setState() {}, postMessage(message) { window.messages.push(message); } });
  });
  await page.addStyleTag({ path: path.join(media, "editor.css") });
  for (const file of ["schema.js", "presentation.js", "variables.js", "dependencies.js", "graph-engine/dagre.min.js", "graph-editor.js", "editor.js"]) await page.addScriptTag({ path: path.join(media, file) });
  let version = 1;
  async function state(extra = {}) {
    await page.evaluate(message => window.dispatchEvent(new MessageEvent("message", { data: message })), {
      type: "state", mode: "configuration", logical: true, filename: "Demo", schema, value, selection,
      variables,
      locked: [], annotations: [], version: version++, dirty: false, ...extra,
    });
  }
  await state();
  const edits = () => page.evaluate(() => window.messages.filter(message => message.type === "edit"));
  const field = name => page.getByLabel(name, { exact: true });
  return { page, field, edits, state, value };
}

test("form orders scalar fields first, follows root priorities and preserves step order", options, async t => {
  const h = await form(t, { workflows: {}, project: { name: "Demo" }, jobs: { build: { env: {}, steps: {zeta: { run: "echo first" }, alpha: { run: "echo second" }}, audience: "all", help: "Build" } }, repository: { alias: "demo" }, ptk_version: ">=1" }, []);
  assert.deepEqual(await h.page.locator("label.name").allTextContents(), ["ptk_version", "repository", "project", "jobs", "workflows"]);
  const navigate = selection => h.page.evaluate(selection => window.dispatchEvent(new MessageEvent("message", { data: { type: "navigate", selection } })), selection);
  await navigate(["jobs", "build"]);
  assert.deepEqual(await h.page.locator("label.name").allTextContents(), ["help", "audience", "env", "steps"]);
  const options = await h.page.getByRole("combobox", { name: "Optional field", exact: true }).locator("option").allTextContents();
  assert.ok(options.indexOf("open_report") < options.indexOf("only_variants"));
  await navigate(["jobs", "build", "steps"]);
  assert.deepEqual(await h.page.locator("label.name").allTextContents(), ["zeta", "alpha"]);
  assert.deepEqual(await h.edits(), []);
});

test("parameter form names all parallel variants without pre-filling dynamic overrides", options, async t => {
  const h = await form(t);
  await h.state({ mode: "parameters", name: "build", project: "demo", variants: ["small", "large"], params: [{ name: "output", type: "str", default: "${vh.variant}", default_is_template: true }] });
  assert.match(await h.page.locator("header").innerText(), /Variants \(parallel\): small, large/);
  assert.match(await h.page.locator("main").innerText(), /resolved separately for each run/);
  assert.equal(await h.page.getByRole("checkbox", { name: "Override output" }).isChecked(), false);
  await h.page.getByRole("button", { name: "Run job", exact: true }).click();
  assert.deepEqual(await h.page.evaluate(() => window.messages.at(-1).params), {});
});

test("compact rows fit more fields and schema help is accessible without editing", options, async t => {
  const h = await form(t, { jobs: { build: { help: "Build the project", only_cx: false, audience: "all", open_report: "on_errors", env: {}, params: {}, requires_tools: {}, steps: {compile: { run: "make" }} } } }, ["jobs", "build"]);
  const rows = await h.page.locator(".field").evaluateAll(rows => rows.map(row => row.getBoundingClientRect().height));
  assert.ok(rows.every(height => height <= 55), JSON.stringify(rows));
  assert.equal(await h.page.getByRole("button", { name: "Add field", exact: true }).isVisible(), true);
  const toggle = h.page.getByRole("button", { name: "Help for only_cx", exact: true });
  assert.equal(await toggle.getAttribute("aria-expanded"), "false");
  await toggle.focus(); await toggle.press("Enter");
  assert.equal(await toggle.getAttribute("aria-expanded"), "true");
  const section = h.page.locator(".field").filter({ has: h.field("only_cx") });
  assert.match(await section.locator(".field-help").innerText(), /hidden from local command/);
  assert.match(await section.locator(".field-help").innerText(), /Default: false/);
  const described = (await h.field("only_cx").getAttribute("aria-describedby")).split(" ");
  assert.ok(described.includes(await section.locator(".field-help").getAttribute("id")));
  await h.state();
  assert.equal(await toggle.getAttribute("aria-expanded"), "true");
  assert.equal((await h.edits()).length, 0);
});

test("compact configuration reflows in narrow editors and displays optional-field help", options, async t => {
  const h = await form(t, { jobs: { build: { steps: {compile: { run: "make", timeout: 30, retries: 2 }} } } }, ["jobs", "build", "steps", "compile"]);
  await h.page.setViewportSize({ width: 380, height: 850 });
  await h.page.getByRole("combobox", { name: "Optional field", exact: true }).selectOption("passthrough");
  assert.match(await h.page.locator(".add .help").innerText(), /--args-for/);
  assert.equal(await h.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  const label = await h.page.locator("label.name").filter({ hasText: /^run$/ }).boundingBox();
  const input = await h.field("run").boundingBox();
  assert.ok(input.y >= label.y + label.height);
  await h.page.getByRole("button", { name: "Help for timeout", exact: true }).click();
  assert.match(await h.page.locator(".field-help:not([hidden])").innerText(), /seconds/);
});

test("slow typing stays local until blur and the editor has no duplicate navigation sidebar", options, async t => {
  const h = await form(t);
  assert.equal(await h.page.locator("nav").count(), 0);
  const first = h.field("first");
  await first.fill("");
  await first.pressSequentially("hello", { delay: 300 });
  assert.equal((await h.edits()).length, 0);
  assert.equal(await first.inputValue(), "hello");
  assert.equal(await first.evaluate(input => document.activeElement === input), true);
  await h.field("second").focus();
  const [edit] = await h.edits();
  assert.deepEqual(edit.operations, [{ op: "set", path: ["vars", "first"], value: "hello" }]);
});

test("a previous field's save acknowledgement neither submits nor replaces the active input", options, async t => {
  const h = await form(t);
  await h.field("first").fill("saved first");
  await h.field("second").focus();
  const [edit] = await h.edits();
  await h.field("second").fill("still typing");
  await h.field("second").evaluate(input => { window.activeInput = input; input.setSelectionRange(5, 5); });
  h.value.vars.first = "saved first";
  await h.state({ ack: edit.id });
  assert.equal((await h.edits()).length, 1);
  assert.deepEqual(await h.field("second").evaluate(input => [input === window.activeInput, document.activeElement === input, input.value, input.selectionStart]), [true, true, "still typing", 5]);
  await h.field("second").press("Control+s");
  assert.equal((await h.edits()).length, 2);
  assert.equal((await h.edits())[1].operations[0].value, "still typing");
});

test("structural save acknowledgements retain active drafts, focus and cursor position", options, async t => {
  const h = await form(t);
  await h.page.locator(".field").filter({ has: h.field("unused") }).getByRole("button", { name: "Remove", exact: true }).click();
  const [edit] = await h.edits();
  await h.field("second").fill("typing during removal");
  await h.field("second").evaluate(input => input.setSelectionRange(6, 6));
  delete h.value.vars.unused;
  await h.state({ ack: edit.id });
  assert.equal((await h.edits()).length, 1);
  assert.deepEqual(await h.field("second").evaluate(input => [document.activeElement === input, input.value, input.selectionStart]), [true, "typing during removal", 6]);
  assert.equal(await h.field("unused").count(), 0);
});

test("failed saves retain the entered value and do not retry automatically", options, async t => {
  const h = await form(t);
  await h.field("first").fill("keep my edit");
  await h.field("second").focus();
  const [edit] = await h.edits();
  await h.state({ ack: edit.id, issue: "Source file changed. Review before saving." });
  assert.equal(await h.field("first").inputValue(), "keep my edit");
  assert.equal((await h.edits()).length, 1);
  assert.match(await h.page.locator("#issue").textContent(), /Source file changed/);
});

test("a rejected connection does not trap the editor in a retry before the next selection", options, async t => {
  const h = await form(t, { jobs: { build: { steps: {check: {run: "check"}, test: {run: "test"}} } } }, ["jobs", "build", "steps", "test"]);
  await h.page.getByLabel("Add prerequisite", { exact: true }).selectOption("check");
  await h.page.getByRole("button", { name: "Connect", exact: true }).click();
  const [edit] = await h.edits();
  await h.state({ ack: edit.id, issue: "Source changed. Review the refreshed configuration." });
  assert.equal(await h.page.locator(".dependency-edge").count(), 0);
  await h.page.getByLabel("Select step", { exact: true }).selectOption("check");
  assert.equal(await h.field("run").inputValue(), "check");
  assert.equal((await h.edits()).length, 1);
  await h.page.getByLabel("Add prerequisite", { exact: true }).selectOption("test");
  await h.page.getByRole("button", { name: "Connect", exact: true }).click();
  assert.equal((await h.edits()).length, 2);
  assert.equal((await h.edits())[1].operations[0].prerequisite, "test");
});

test("workflow job selection excludes duplicates and adding a reused target makes no edit", options, async t => {
  const h = await form(t, { repository: { alias: "app" }, jobs: {check: {steps: {}}, test: {steps: {}}}, workflows: {verify: {jobs: {a: {job: "check"}, b: {job: "app:check"}}}} }, ["workflows", "verify", "jobs", "b"]);
  assert.match(await h.page.locator(".dependency-editor [role=alert]").innerText(), /only be chosen once/);
  assert.deepEqual(await h.page.locator("datalist option").evaluateAll(options => options.map(option => option.value)), ["test"]);
  await h.field("job").fill("test"); await h.field("job").blur();
  const [edit] = await h.edits();
  h.value.workflows.verify.jobs.b.job = "test";
  await h.state({ ack: edit.id });
  assert.equal(await h.page.locator(".dependency-node").count(), 2);
  await h.page.evaluate(() => window.dispatchEvent(new MessageEvent("message", { data: { type: "navigate", selection: ["workflows", "verify", "jobs"] } })));
  await h.page.getByLabel("New field name", { exact: true }).fill("third");
  await h.page.getByLabel("Job to add", { exact: true }).fill("app:check");
  await h.page.getByRole("button", { name: "Add field", exact: true }).click();
  assert.match(await h.page.locator("#issue").innerText(), /only be chosen once/);
  assert.equal((await h.edits()).length, 1);
  await h.page.getByLabel("Job to add", { exact: true }).fill("other:check");
  await h.page.getByRole("button", { name: "Add field", exact: true }).click();
  assert.equal((await h.edits()).length, 2);
  assert.equal((await h.edits())[1].operations[0].value.job, "other:check");
});

test("editing a needs field detects a loop without leaving the configuration form", options, async t => {
  const h = await form(t, {jobs: {build: {steps: {a: {run: "a", needs: []}, b: {run: "b", needs: "a"}}}}}, ["jobs", "build", "steps", "b"]);
  await h.field("needs").fill("b"); await h.field("needs").blur();
  const [edit] = await h.edits();
  h.value.jobs.build.steps.b.needs = "b";
  await h.state({ ack: edit.id });
  assert.match(await h.page.locator(".dependency-editor [role=alert]").innerText(), /itself/);
  assert.equal(await h.field("run").inputValue(), "b");
});

test("tree navigation opens named step fields with readable breadcrumbs", options, async t => {
  const h = await form(t, { jobs: { build: { steps: {compile: { run: "make" }} } } }, ["jobs", "build", "steps"]);
  assert.deepEqual(await h.page.locator("label.name").allTextContents(), ["compile"]);
  await h.page.evaluate(() => window.dispatchEvent(new MessageEvent("message", { data: { type: "navigate", selection: ["jobs", "build", "steps", "compile"] } })));
  assert.equal(await h.field("run").inputValue(), "make");
  assert.deepEqual(await h.page.locator(".crumbs button").allTextContents(), ["Configuration", "jobs", "build", "steps", "compile"]);
});

test("invalid graph configuration keeps fields and raw YAML usable and recovers after repair", options, async t => {
  const h = await form(t, { jobs: { build: { steps: {check: {run: "check"}, test: {run: "test", needs: ["missing"]}} } } }, ["jobs", "build", "steps", "test"]);
  assert.match(await h.page.locator(".dependency-editor [role=alert]").innerText(), /unknown prerequisite/);
  assert.equal(await h.field("run").inputValue(), "test");
  assert.equal(await h.page.getByRole("button", { name: "Raw YAML", exact: true }).isEnabled(), true);
  await h.page.getByRole("button", { name: "Remove prerequisite missing from test" }).click();
  const [edit] = await h.edits();
  h.value.jobs.build.steps.test.needs = [];
  await h.state({ ack: edit.id });
  assert.equal(await h.page.locator(".dependency-node").count(), 2);
  h.value.jobs.build.steps.test.title = { invalid: "field type" };
  h.value.jobs.build.steps.test.needs = ["check"];
  h.value.jobs.build.steps.check.needs = ["test"];
  await h.state({ validationError: "Configuration validation failed: cycle and invalid title" });
  assert.match(await h.page.locator("#validation-error").innerText(), /validation failed/);
  assert.match(await h.page.locator(".dependency-editor [role=alert]").innerText(), /cycle/);
  await h.page.getByRole("button", { name: "Remove prerequisite check from test" }).click();
  const last = (await h.edits()).at(-1);
  h.value.jobs.build.steps.test.needs = [];
  await h.state({ ack: last.id, validationError: "title must be a string" });
  assert.equal(await h.page.locator(".dependency-node").count(), 2);
  assert.equal(await h.field("run").inputValue(), "test");
  h.value.jobs.build.steps.test.needs = 17;
  await h.state({ validationError: "needs must be a name or list" });
  assert.match(await h.page.locator(".dependency-editor [role=alert]").innerText(), /needs must be a name or list/);
  assert.equal(await h.field("needs").inputValue(), "17");
  assert.equal(await h.page.getByRole("button", { name: "Save & validate", exact: true }).isEnabled(), true);
  h.value.jobs.build.steps.test.needs = [];
  await h.page.evaluate(() => { window.savedGraphMount = PtkGraphEditor.mount; PtkGraphEditor.mount = () => { throw new Error("layout failed"); }; });
  await h.state();
  assert.match(await h.page.getByRole("alert").filter({ hasText: "Graph could not be displayed" }).innerText(), /layout failed/);
  assert.equal(await h.field("run").inputValue(), "test");
  await h.page.evaluate(() => { PtkGraphEditor.mount = window.savedGraphMount; });
  await h.state();
  assert.equal(await h.page.locator(".dependency-node").count(), 2);
});

test("save notifications arriving during another edit do not release its pending acknowledgement", options, async t => {
  const h = await form(t);
  await h.field("first").fill("first change");
  await h.field("second").focus();
  const [edit] = await h.edits();
  await h.field("second").fill("second change");
  await h.field("unused").focus();
  await h.state({ reason: "saved" });
  assert.equal((await h.edits()).length, 1);
  h.value.vars.first = "first change";
  await h.state({ ack: edit.id });
  assert.equal((await h.edits()).length, 2);
  assert.equal((await h.edits())[1].operations[0].value, "second change");
});

test("an unfinished numeric value survives a structural acknowledgement", options, async t => {
  const h = await form(t, { vars: { first: 7, unused: "remove me" } });
  await h.page.locator(".field").filter({ has: h.field("unused") }).getByRole("button", { name: "Remove", exact: true }).click();
  const [edit] = await h.edits();
  await h.field("first").fill("");
  delete h.value.vars.unused;
  await h.state({ ack: edit.id });
  assert.equal(await h.field("first").inputValue(), "");
  assert.equal(await h.field("first").getAttribute("aria-invalid"), "true");
  assert.equal(await h.field("first").evaluate(input => document.activeElement === input), true);
  assert.equal((await h.edits()).length, 1);
});

test("adding a second named step during a save retains its name and required fields", options, async t => {
  const h = await form(t, {jobs: {build: {steps: {}}}}, ["jobs", "build", "steps"]);
  const name = h.page.getByRole("textbox", {name: "New field name", exact: true});
  await name.fill("first"); await h.page.getByRole("button", {name: "Add field", exact: true}).click();
  const [first] = await h.edits();
  await name.fill("second"); await h.page.getByRole("button", {name: "Add field", exact: true}).click();
  h.value.jobs.build.steps.first = first.operations[0].value;
  await h.state({ack: first.id});
  const second = (await h.edits())[1];
  assert.equal(second.operations[0].path.at(-1), "second");
  assert.deepEqual(first.operations[0].value, {run: "echo Hello"});
  assert.deepEqual(second.operations[0].value, {run: "echo Hello"});
});

test("a structural reply retains the next add-field name and caret", options, async t => {
  const h = await form(t);
  const name = h.page.getByRole("textbox", { name: "New field name", exact: true });
  await name.fill("third");
  await h.page.getByRole("button", { name: "Add field", exact: true }).click();
  const [edit] = await h.edits();
  await name.fill("fourth");
  await name.evaluate(input => input.setSelectionRange(3, 3));
  h.value.vars.third = "";
  await h.state({ ack: edit.id });
  assert.deepEqual(await name.evaluate(input => [input.value, document.activeElement === input, input.selectionStart]), ["fourth", true, 3]);
});

test("tree navigation does not discard an add action queued behind a scalar save", options, async t => {
  const h = await form(t);
  await h.field("first").fill("changed");
  await h.page.getByRole("textbox", { name: "New field name", exact: true }).fill("third");
  const [edit] = await h.edits();
  await h.page.getByRole("button", { name: "Add field", exact: true }).click();
  await h.page.evaluate(() => window.dispatchEvent(new MessageEvent("message", { data: { type: "navigate", selection: [] } })));
  h.value.vars.first = "changed";
  await h.state({ ack: edit.id });
  assert.deepEqual((await h.edits())[1]?.operations[0].path, ["vars", "third"]);
});

test("a reply between pointer down and click cannot eat an Add field click", options, async t => {
  const h = await form(t);
  await h.page.locator(".field").filter({ has: h.field("unused") }).getByRole("button", { name: "Remove", exact: true }).click();
  const [edit] = await h.edits();
  await h.page.getByRole("textbox", { name: "New field name", exact: true }).fill("third");
  const box = await h.page.getByRole("button", { name: "Add field", exact: true }).boundingBox();
  await h.page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await h.page.mouse.down();
  delete h.value.vars.unused;
  await h.state({ ack: edit.id });
  await h.page.mouse.up();
  assert.deepEqual((await h.edits())[1]?.operations[0].path, ["vars", "third"]);
});

test("empty text fields show a red fill-in cue that clears immediately on input", options, async t => {
  const h = await form(t, { project: { name: "", description: "" } }, ["project"]);
  const name = h.field("name");
  const section = h.page.locator(".field").filter({ has: name });
  assert.equal(await name.getAttribute("aria-required"), "true");
  assert.equal(await name.getAttribute("aria-invalid"), "true");
  assert.match(await section.getAttribute("class"), /needs-value/);
  assert.equal(await section.locator(".empty-field-message").innerText(), "Required — enter a value.");
  await name.fill("Demo");
  assert.doesNotMatch(await section.getAttribute("class"), /needs-value/);
  assert.equal(await name.getAttribute("aria-invalid"), null);
  assert.equal(await section.locator(".empty-field-message").isVisible(), false);
  assert.equal((await h.edits()).length, 0);
  await h.field("description").focus();
  assert.equal((await h.edits()).length, 1);
});

test("zero and false are filled values rather than empty fields", options, async t => {
  const h = await form(t, { vars: { count: 0, enabled: false, empty: "" } });
  const empty = h.page.locator(".needs-value label.name");
  assert.deepEqual(await empty.allTextContents(), ["empty"]);
});

test("variable picker inserts at the caret without saving or losing the draft", options, async t => {
  const h = await form(t);
  const input = h.field("first"), section = h.page.locator(".field").filter({ has: input });
  await input.fill("prefix-/suffix");
  await input.evaluate(input => input.setSelectionRange(7, 7));
  await section.getByRole("button", { name: "Insert variable…", exact: true }).click();
  await section.getByRole("searchbox").fill("git short");
  await section.locator(".variable-results").getByRole("option").click();
  assert.equal(await input.inputValue(), "prefix-${git.short_commit}/suffix");
  assert.equal(await input.evaluate(input => document.activeElement === input), true);
  assert.equal((await h.edits()).length, 0);
  await h.field("second").focus();
  assert.equal((await h.edits()).length, 1);
  assert.equal((await h.edits())[0].operations[0].value, "prefix-${git.short_commit}/suffix");
});

test("typing a template completes with the keyboard and escaped templates stay literal", options, async t => {
  const h = await form(t);
  const input = h.field("first");
  await input.fill("out/${git.sh");
  assert.equal(await h.page.locator(".variable-picker:not([hidden]) .variable-option").count(), 1);
  await input.press("Enter");
  assert.equal(await input.inputValue(), "out/${git.short_commit}");
  assert.equal((await h.edits()).length, 0);
  await input.fill("$${git.sh");
  assert.equal(await h.page.locator(".variable-picker:not([hidden])").count(), 0);
});

test("environment insertion selects the name placeholder and Escape preserves the input", options, async t => {
  const h = await form(t);
  const input = h.field("first"), section = h.page.locator(".field").filter({ has: input });
  await input.fill("${env:NA");
  await input.press("Enter");
  assert.equal(await input.inputValue(), "${env:NAME}");
  assert.equal(await input.evaluate(input => input.value.slice(input.selectionStart, input.selectionEnd)), "NAME");
  await section.getByRole("button", { name: "Insert variable…", exact: true }).click();
  await section.getByRole("searchbox").press("Escape");
  assert.equal(await input.inputValue(), "${env:NAME}");
  assert.equal((await h.edits()).length, 0);
});

test("structural acknowledgements wait for the picker and retain the inserted value", options, async t => {
  const h = await form(t);
  await h.page.locator(".field").filter({ has: h.field("unused") }).getByRole("button", { name: "Remove", exact: true }).click();
  const [edit] = await h.edits();
  const input = h.field("first");
  await input.fill("${git.sh");
  delete h.value.vars.unused;
  await h.state({ ack: edit.id });
  assert.equal(await input.inputValue(), "${git.sh");
  await input.press("Enter");
  assert.equal(await h.field("first").inputValue(), "${git.short_commit}");
  assert.equal((await h.edits()).length, 1);
  assert.equal(await h.field("unused").count(), 0);
});

test("literal fields do not offer variable insertion and keyboard opening does not save", options, async t => {
  const h = await form(t, { project: { name: "demo" } }, ["project"]);
  assert.equal(await h.page.getByRole("button", { name: "Insert variable…", exact: true }).count(), 0);
  await h.state({ value: { vars: { first: "" } }, selection: ["vars"] });
  await h.page.evaluate(() => window.dispatchEvent(new MessageEvent("message", { data: { type: "navigate", selection: ["vars"] } })));
  await h.field("first").fill("draft");
  await h.field("first").press("Tab");
  await h.page.keyboard.press("Enter");
  assert.equal(await h.page.getByRole("searchbox").isVisible(), true);
  assert.equal((await h.edits()).length, 0);
});

test("run form shows authored choices and help and submits one variant batch", options, async t => {
  const { builtinParam } = require("./fixtures");
  const h = await form(t);
  await h.state({ mode: "parameters", kind: "job", name: "build", project: "demo", variants: ["small"], defaultVariant: "small",
    variantChoices: [{ name: "small", description: "Quick developer build", aliases: ["dev"] }, { name: "large", description: "Full build" }],
    runOptions: [
      builtinParam("only_step", { kind: "option", option: "--only-step", help: "Run only this step, bypassing prerequisites.", choices: ["configure", "compile"], suggestions: [{ value: "configure", help: "Prepare build files" }] }),
      builtinParam("end", { kind: "option", option: "--to", help: "Run this step and its prerequisites.", choices: ["configure", "compile"] }),
      builtinParam("features", { kind: "option", option: "--feature", multiple: true, help: "Override a variant feature.", suggestions: [{ value: "MODE=", help: "Compilation mode" }] }),
    ], params: [{ name: "mode", type: "choice", choices: ["Debug", "Release"], help: "Choose compiler optimization", default: "Debug" }],
  });
  assert.match(await h.page.locator("main").innerText(), /Quick developer build/);
  assert.match(await h.page.locator("main").innerText(), /Aliases: dev/);
  assert.deepEqual(await h.field("--only-step").locator("option").allTextContents(), ["Use default", "configure — Prepare build files", "compile"]);
  await h.field("--only-step").selectOption("configure");
  await h.page.getByRole("checkbox", { name: "small", exact: true }).check();
  await h.page.getByRole("checkbox", { name: "large", exact: true }).check();
  assert.equal(await h.page.getByRole("checkbox", { name: "All variants", exact: true }).isChecked(), true);
  assert.equal(await h.field("mode").isDisabled(), true);
  await h.page.getByText("More run options", { exact: true }).click();
  await h.page.getByRole("button", { name: "MODE=", exact: true }).click();
  assert.equal(await h.field("--feature").inputValue(), "MODE=");
  await h.field("--feature").fill("MODE=fast");
  await h.page.setViewportSize({ width: 390, height: 850 });
  assert.equal(await h.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await h.page.screenshot({ path: "/tmp/ptk-run-options-narrow.png", fullPage: true });
  await h.page.getByRole("button", { name: "Dry run", exact: true }).click();
  const message = await h.page.evaluate(() => window.messages.at(-1));
  assert.deepEqual(message.variants, ["small", "large"]);
  assert.deepEqual(message.runOptions, { only_step: ["configure"], features: ["MODE=fast"] });
  assert.deepEqual(message.params, {});
  assert.equal(message.preview, true);
});

test("workflow run form supports all owner variants and automatic default selection", options, async t => {
  const h = await form(t);
  await h.state({ mode: "parameters", kind: "workflow", name: "verify", help: "Run all validation jobs", project: "demo", variants: ["small"],
    variantChoices: [{ name: "small" }, { name: "large" }], defaultVariant: "small", runOptions: [], params: [] });
  assert.match(await h.page.locator("main").innerText(), /Run all validation jobs/);
  await h.page.getByRole("checkbox", { name: "All variants", exact: true }).check();
  assert.equal(await h.page.getByRole("checkbox", { name: "small", exact: true }).isChecked(), true);
  await h.page.getByRole("checkbox", { name: "All variants", exact: true }).uncheck();
  assert.equal(await h.page.getByRole("checkbox", { name: "small", exact: true }).isChecked(), true);
  await h.page.getByRole("checkbox", { name: "large", exact: true }).check();
  assert.equal(await h.page.getByRole("combobox").count(), 0);
  await h.page.getByRole("button", { name: "Run workflow", exact: true }).click();
  const message = await h.page.evaluate(() => window.messages.at(-1));
  assert.deepEqual(message.variants, ["small", "large"]);
  assert.deepEqual(message.runOptions, {});
  assert.equal(message.preview, false);
});

test("workflow invocation editor exposes qualified jobs and needs without step groups", options, async t => {
  const value = { workflows: { verify: { jobs: { compile: { job: "my_repo:build" }, test: { job: "my_repo:test", needs: "compile" } } } } };
  const h = await form(t, value, ["workflows", "verify", "jobs", "test"]);
  assert.equal(await h.field("job").inputValue(), "my_repo:test");
  assert.equal(await h.field("needs").inputValue(), "compile");
  await h.page.getByRole("button", { name: "Help for needs", exact: true }).click();
  assert.match(await h.page.locator(".field-help:not([hidden])").innerText(), /Invocation IDs/);
  const optional = await h.page.getByRole("combobox", { name: "Optional field", exact: true }).locator("option").allTextContents();
  assert.ok(optional.includes("params") && optional.includes("continue_on_error"));
  assert.ok(!optional.some(name => ["repo", "parallel", "steps"].includes(name)));
  await h.field("job").fill("backend_repo:run_tests");
  await h.field("job").blur();
  const edits = await h.edits();
  assert.deepEqual(edits.at(-1).operations[0].path, ["workflows", "verify", "jobs", "test", "job"]);
  assert.equal(edits.at(-1).operations[0].value, "backend_repo:run_tests");
});

test("job and step configuration explain outputs and optional cache before opt-in", options, async t => {
  const value = {jobs: {build: {steps: {compile: {run: "make"}}}}};
  const h = await form(t, value, ["jobs", "build"]);
  const guidance = h.page.locator("[data-output-guidance]");
  assert.match(await guidance.innerText(), /uploads and downloads in workflows/);
  assert.match(await guidance.innerText(), /project owns the output declarations and cache correctness/);
  await h.state({selection: ["jobs", "build", "steps", "compile"]});
  assert.match(await guidance.innerText(), /optional aid/);
  assert.match(await guidance.innerText(), /--no-cache-ptk/);
  assert.deepEqual(await h.edits(), []);
});
