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
  for (const file of ["schema.js", "presentation.js", "variables.js", "editor.js"]) await page.addScriptTag({ path: path.join(media, file) });
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

test("tree navigation opens named step fields with readable breadcrumbs", options, async t => {
  const h = await form(t, { jobs: { build: { steps: [{ compile: { run: "make" } }] } } }, ["jobs", "build", "steps"]);
  assert.deepEqual(await h.page.locator("label.name").allTextContents(), ["compile"]);
  await h.page.evaluate(() => window.dispatchEvent(new MessageEvent("message", { data: { type: "navigate", selection: ["jobs", "build", "steps", 0, "compile"] } })));
  assert.equal(await h.field("run").inputValue(), "make");
  assert.deepEqual(await h.page.locator(".crumbs button").allTextContents(), ["Configuration", "jobs", "build", "steps", "compile"]);
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

test("adding a second list item during a save uses the acknowledged list position", options, async t => {
  const h = await form(t, { jobs: { build: { steps: [] } } }, ["jobs", "build", "steps"]);
  await h.page.getByRole("button", { name: "Add item", exact: true }).click();
  const [first] = await h.edits();
  await h.page.getByRole("button", { name: "Add item", exact: true }).click();
  h.value.jobs.build.steps.push(first.operations[0].value);
  await h.state({ ack: first.id });
  const second = (await h.edits())[1];
  assert.equal(second.operations[0].path.at(-1), 1);
  assert.notDeepEqual(Object.keys(second.operations[0].value), Object.keys(first.operations[0].value));
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
