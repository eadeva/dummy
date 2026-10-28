"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const path = require("node:path");
let chromium;
try { ({ chromium } = require(process.env.PTK_TEST_PLAYWRIGHT || "playwright")); } catch {}
const options = { skip: !chromium && "Install Playwright or set PTK_TEST_PLAYWRIGHT for real webview tests" };
const media = path.resolve(__dirname, "../media");
const schema = require("../media/config-schema.json");

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
  for (const file of ["schema.js", "presentation.js", "editor.js"]) await page.addScriptTag({ path: path.join(media, file) });
  let version = 1;
  async function state(extra = {}) {
    await page.evaluate(message => window.dispatchEvent(new MessageEvent("message", { data: message })), {
      type: "state", mode: "configuration", logical: true, filename: "Demo", schema, value, selection,
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
