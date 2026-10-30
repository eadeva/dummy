"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const { spawnSync } = require("node:child_process");
const { pathToFileURL } = require("node:url");
let chromium;
try { ({ chromium } = require(process.env.PTK_TEST_PLAYWRIGHT || "playwright")); } catch {}
const python = process.env.PTK_TEST_PYTHON;
const repo = path.resolve(__dirname, "../../..");

test("offline graphs in previews, job and workflow reports preserve joins, states and interactive controls", { skip: !python || !chromium ? "Requires PTK_TEST_PYTHON and Playwright" : false }, async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk graphs "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const result = spawnSync(python, [path.join(repo, "scripts/graph_preview.py"), root], { cwd: repo, encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repo, "src") }, timeout: 30000 });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = [], requests = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route(/^https?:/, route => { requests.push(route.request().url()); return route.abort(); });
  for (const file of ["job.html", "workflow.html", "graph.html"]) {
    await page.goto(pathToFileURL(path.join(root, file)).href);
    const graph = page.locator(".ptk-graph");
    assert.equal(await graph.evaluate(node => node.open), file === "graph.html");
    if (file !== "graph.html") {
      assert.equal(await graph.locator(".ptk-graph-node").count(), 0);
      await graph.locator("summary").click();
    }
    await page.waitForFunction(() => document.querySelectorAll(".ptk-graph-node").length === 6);
    if (file === "graph.html") assert.equal(await graph.locator(".ptk-graph-subtitle").count(), 0);
    assert.equal(await graph.locator(".ptk-graph-edge").count(), 5);
    assert.equal(await graph.locator('[data-node-id="compile"]').count(), 1);
    assert.equal(await graph.locator('[data-from="compile"]').count(), 2);
    assert.equal(await graph.locator('[data-to="compile"]').count(), 1);
    assert.equal(await graph.locator('[data-status="failed"]').count(), 2);
    assert.equal(await graph.locator('[data-allowed="true"]').count(), 1);
    assert.equal(await graph.locator('[data-status="cancelled"]').count(), 1);
    assert.equal(await graph.locator('[data-status="skipped"]').count(), 1);
    const packageNode = graph.locator('[data-node-id="package"]');
    await packageNode.focus(); await packageNode.press("Enter");
    assert.match(await graph.locator(".ptk-graph-inspector").innerText(), /Blocked by documentation/);
    await graph.locator(".ptk-graph-inspector").getByRole("button", { name: "documentation", exact: true }).click();
    assert.equal(await graph.locator('[data-node-id="documentation"]').getAttribute("aria-pressed"), "true");
    assert.match(await graph.locator(".ptk-graph-inspector").innerText(), /<script>window.injected=true<\/script>/);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    const before = await graph.locator("output").textContent();
    await graph.getByRole("button", { name: "Zoom in", exact: true }).click();
    assert.notEqual(await graph.locator("output").textContent(), before);
    await graph.getByRole("button", { name: "Fit to view", exact: true }).click();
    const geometry = await graph.locator(".ptk-graph-node").evaluateAll(nodes => nodes.map(node => ({ id: node.dataset.nodeId, x: node.transform.baseVal.getItem(0).matrix.e, y: node.transform.baseVal.getItem(0).matrix.f, width: node.querySelector("rect").width.baseVal.value, height: node.querySelector("rect").height.baseVal.value })));
    for (const [i, box] of geometry.entries()) for (const other of geometry.slice(i + 1)) assert(box.x + box.width <= other.x || other.x + other.width <= box.x || box.y + box.height <= other.y || other.y + other.height <= box.y, `Overlap: ${box.id}, ${other.id}`);
    const edges = await graph.locator(".ptk-graph-edge").evaluateAll(edges => edges.map(edge => ({from: edge.dataset.from, to: edge.dataset.to})));
    for (const edge of edges) {
      const from = geometry.find(node => node.id === edge.from), to = geometry.find(node => node.id === edge.to);
      assert(from.y + from.height < to.y, `${edge.from} must appear above ${edge.to}`);
    }
    await graph.locator("summary").click(); await graph.locator("summary").click();
    assert.equal(await graph.locator(".ptk-graph-node").count(), 6);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.equal(await graph.locator("svg").getAttribute("viewBox").then(value => value.includes("NaN")), false);
    await page.emulateMedia({ colorScheme: "light" });
    await page.setViewportSize({ width: 1280, height: 1000 });
  }
  await page.goto(pathToFileURL(path.join(root, "wide.html")).href);
  assert.equal(await page.locator(".ptk-graph-node").count(), 25);
  assert.equal(await page.locator(".ptk-graph-edge").count(), 24);
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  const viewport = page.locator(".ptk-graph-viewport");
  const bounds = await viewport.boundingBox();
  await viewport.evaluate(node => { node.scrollLeft = 0; });
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height - 30);
  await page.mouse.down(); await page.mouse.move(bounds.x + bounds.width / 2 - 100, bounds.y + bounds.height - 30); await page.mouse.up();
  assert(await viewport.evaluate(node => node.scrollLeft > 0));
  await page.goto(pathToFileURL(path.join(root, "empty.html")).href);
  assert.match(await page.locator(".ptk-graph-viewport").innerText(), /No dependencies recorded/);
  assert.equal(await page.locator(".ptk-graph-toolbar").isVisible(), false);
  assert.deepEqual(errors, []);
  assert.deepEqual(requests, []);
});
