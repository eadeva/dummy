"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs/promises"), path = require("node:path");
const { harness } = require("./editor-harness");
const model = require("../src/config-model");
let chromium;
try { ({ chromium } = require(process.env.PTK_TEST_PLAYWRIGHT || "playwright")); } catch {}
const media = path.resolve(__dirname, "../media");
const theme = ":root{--vscode-foreground:#d4d7df;--vscode-editor-background:#181c24;--vscode-font-family:system-ui;--vscode-font-size:13px;--vscode-descriptionForeground:#a6b0c1;--vscode-input-background:#242b38;--vscode-input-foreground:#e7eaf0;--vscode-panel-border:#424c60;--vscode-focusBorder:#ab99ff;--vscode-charts-blue:#6db5f6;--vscode-button-background:#7361ce;--vscode-button-foreground:white;--vscode-button-secondaryBackground:#2b3342;--vscode-button-secondaryForeground:#e7eaf0;--vscode-errorForeground:#ff9b9b}";

test("shipped graph is a view after the fields; dependencies change only through fields", { skip: !chromium && "Requires Playwright" }, async t => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1180, height: 1100 } });
  const errors = [], requests = [];
  page.on("pageerror", error => errors.push(error.message));
  const original = "# My project\njobs:\n  build:\n    steps:\n      check: {run: check}\n      test: {run: test, needs: [check]}\n      package: {run: package, needs: [test]}\n      docs: {run: docs}\nworkflows:\n  verify:\n    jobs:\n      build: {}\n      other:deploy: {needs: [build]}\n";
  const h = harness(original);
  const panel = await h.resolve();
  await h.editors.open(h.document.uri, ["jobs", "build", "steps", "package"]);
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://ptk.test") { requests.push(url.href); return route.abort(); }
    if (url.pathname === "/index.html") return route.fulfill({ contentType: "text/html", body: panel.webview.html });
    const body = await fs.readFile(path.join(media, url.pathname.slice(1)));
    return route.fulfill({ contentType: url.pathname.endsWith("css") ? "text/css" : "application/javascript", body: url.pathname.endsWith("css") ? Buffer.concat([Buffer.from(theme + ":root{--vscode-charts-blue:#3366ee;--vscode-terminal-ansiCyan:#008b8b}"), body]) : body });
  });
  await page.exposeFunction("ptkHost", message => panel.receive(message));
  await page.addInitScript(() => { window.acquireVsCodeApi = () => ({ postMessage: message => window.ptkHost(message), getState: () => ({}), setState() {} }); });
  panel.onPost = message => page.evaluate(data => window.dispatchEvent(new MessageEvent("message", { data })), message);
  await page.goto("http://ptk.test/index.html");
  await h.editors.open(h.document.uri, ["jobs", "build", "steps", "package"]);
  await page.locator(".dependency-node").first().waitFor();
  assert.equal(await page.locator(".dependency-editor").getAttribute("data-entity"), "step");
  assert.equal(await page.locator(".dependency-node [aria-pressed=false] rect").first().evaluate(node => getComputedStyle(node).stroke), "rgb(51, 102, 238)");
  assert.equal(await page.locator(".dependency-node").count(), 4);
  assert.equal(await page.locator(".dependency-edge").count(), 2);
  // The graph follows the fields and offers no editing controls.
  assert.ok(await page.evaluate(() => {
    const graph = document.querySelector(".dependency-editor"), fields = [...document.querySelectorAll(".field")];
    return fields.length > 0 && fields.every(field => field.compareDocumentPosition(graph) & Node.DOCUMENT_POSITION_FOLLOWING);
  }));
  for (const selector of [".dependency-outlet", ".dependency-inlet", "#graph-prerequisite"]) assert.equal(await page.locator(selector).count(), 0, selector);
  for (const name of ["Connect", "New step", "New dependent", "New workflow job"]) assert.equal(await page.getByRole("button", { name, exact: true }).count(), 0, name);
  // Dragging between nodes changes nothing.
  const from = await page.locator('.dependency-node[data-node-id="docs"] rect').boundingBox();
  const to = await page.locator('.dependency-node[data-node-id="package"] rect').boundingBox();
  await page.mouse.move(from.x + from.width / 2, from.y + from.height - 2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 12 });
  await page.mouse.up();
  assert.equal(h.edits.length, 0);
  // Prerequisites open the referenced node; the needs field is the way to change them.
  await page.getByRole("button", { name: "Open prerequisite test", exact: true }).click();
  assert.equal(await page.getByLabel("run", { exact: true }).inputValue(), "test");
  await page.getByLabel("Select step", { exact: true }).selectOption("check");
  assert.equal(await page.getByLabel("run", { exact: true }).inputValue(), "check");
  const node = page.getByRole("button", { name: "Edit step package", exact: true });
  await node.focus(); await node.press("Enter");
  assert.equal(await page.getByLabel("run", { exact: true }).inputValue(), "package");
  const zoom = await page.getByLabel("Graph zoom").textContent();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  assert.notEqual(await page.getByLabel("Graph zoom").textContent(), zoom);
  await page.getByRole("button", { name: "Fit", exact: true }).click();
  if (process.env.PTK_UI_SCREENSHOTS) await page.screenshot({ path: path.join(process.env.PTK_UI_SCREENSHOTS, "graph-editor.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 900 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.setViewportSize({ width: 1180, height: 1100 });
  h.external(original);
  await page.waitForFunction(() => document.querySelectorAll(".dependency-edge").length === 2);
  await h.editors.open(h.document.uri, ["workflows", "verify", "jobs", "deploy"]);
  await page.getByLabel("Select job", { exact: true }).waitFor();
  assert.equal(await page.locator(".dependency-editor").getAttribute("data-entity"), "job");
  assert.equal(await page.locator(".dependency-node [aria-pressed=false] rect").first().evaluate(node => getComputedStyle(node).stroke), "rgb(0, 139, 139)");
  assert.equal(await page.getByLabel("Select job", { exact: true }).inputValue(), "deploy");
  assert.match(await page.locator(".dependency-node").last().textContent(), /other:deploy/);
  assert.equal(await page.getByLabel("job", { exact: true }).inputValue(), "other:deploy");
  assert.equal(await page.locator("datalist option").count(), 0);
  // Invalid workflow dependencies are diagnosed; the needs field fixes them and the view follows.
  h.external("workflows:\n  verify:\n    jobs:\n      check: {}\n      test: {}\n      package: {needs: [check, test, extension]}\n      docs: {}\n      extension: {needs: missing}\n");
  await h.editors.open(h.document.uri, ["workflows", "verify", "jobs", "package"]);
  await page.getByRole("alert").filter({ hasText: "unknown prerequisite" }).waitFor();
  await page.getByLabel("Select job", { exact: true }).selectOption("extension");
  assert.equal(await page.getByLabel("needs", { exact: true }).inputValue(), "missing");
  await page.getByLabel("needs", { exact: true }).fill("check");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll(".dependency-node").length === 5);
  assert.equal(model.inspect(h.document.getText()).value.workflows.verify.jobs.extension.needs, "check");
  await page.getByLabel("Select job", { exact: true }).selectOption("package");
  assert.equal(await page.locator(".dependency-edge").count(), 4);
  assert.equal(await page.getByRole("button", { name: "Open prerequisite extension", exact: true }).count(), 1);
  assert.deepEqual(errors, []); assert.deepEqual(requests, []);
});
