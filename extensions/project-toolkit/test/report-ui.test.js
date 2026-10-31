"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const { spawnSync } = require("node:child_process");
let chromium;
try { ({ chromium } = require(process.env.PTK_TEST_PLAYWRIGHT || "playwright")); } catch {}
const python = process.env.PTK_TEST_PYTHON;
const repo = path.resolve(__dirname, "../../..");

test("HTML log analysis filters dispositions and severities, counts occurrences and exposes source evidence", { skip: !python || !chromium ? "Requires PTK_TEST_PYTHON and Playwright" : false }, async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk log analysis "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, "jobs"));
  fs.writeFileSync(path.join(root, ".main.ptk.yml"), "repository: {alias: demo, config_path: .}\n");
  fs.writeFileSync(path.join(root, "project.ptk.yml"), JSON.stringify({ name: "demo", log_analysis: { rules: [
    { id: "sdk", match: { severity: "warning", message_regex: "^Old SDK" }, action: "justify", reason: "Upgrade planned <next>" },
    { id: "expected", match: { message_regex: "^expected failure$" }, action: "ignore", reason: "Negative test" },
  ] } }));
  fs.writeFileSync(path.join(root, "jobs/build.ptk.yml"), JSON.stringify({ steps: {compile: { run: [python, "-c", "print('src/main.cpp:42: error: unresolved motor_start'); print('WARNING: active warning'); print('WARNING: active warning'); print('WARNING: Old SDK'); print('ERROR: expected failure'); print('ERROR: <script>window.injected=true</script>')"] }} }));
  const result = spawnSync(python, ["-m", "ptk", "build"], { cwd: root, encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repo, "src"), PTK_ROLE: "user", PTK_CI: "0" }, timeout: 30000 });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.on("pageerror", error => assert.fail(error.message));
  await page.goto(require("node:url").pathToFileURL(path.join(root, "_reports/default/build/report.html")).href);
  const section = page.locator("#diagnostics");
  assert.equal(await page.evaluate(() => window.injected), undefined);
  assert.equal(await section.getByLabel("Disposition", { exact: true }).inputValue(), "active");
  assert.equal(await section.locator(".diagnostic:visible").count(), 3);
  assert.match(await section.locator("[data-filter-count]").innerText(), /3 of 5 diagnostics shown · 4 log occurrences/);
  assert.equal(await section.locator('[data-diagnostic-card="error"] strong').innerText(), "2");
  assert.equal(await section.locator('[data-diagnostic-card="warning"] strong').innerText(), "2");
  await section.getByLabel("Severity", { exact: true }).selectOption("warning");
  assert.equal(await section.locator(".diagnostic:visible").count(), 1);
  await section.getByRole("button", { name: "Show justified log findings", exact: true }).click();
  assert.equal(await section.getByLabel("Severity", { exact: true }).inputValue(), "");
  assert.equal(await section.getByLabel("Disposition", { exact: true }).inputValue(), "justified");
  const row = section.locator(".diagnostic:visible");
  await row.locator("summary").click();
  assert.match(await row.innerText(), /Upgrade planned <next>/);
  assert.equal(await row.locator("mark").count(), 1);
  const href = await row.getByRole("link", { name: "compile.log" }).getAttribute("href");
  assert.equal(fs.existsSync(path.resolve(root, "_reports/default/build", decodeURIComponent(href))), true);
  await section.getByRole("button", { name: "Show ignored log findings", exact: true }).click();
  assert.equal(await section.locator(".diagnostic:visible").count(), 1);
  await section.getByLabel("Disposition", { exact: true }).selectOption("");
  assert.equal(await section.locator(".diagnostic:visible").count(), 5);
  await section.getByRole("searchbox").fill("motor_start");
  assert.equal(await section.locator(".diagnostic:visible").count(), 1);
  await section.getByRole("button", { name: "Reset filters", exact: true }).click();
  assert.equal(await section.locator(".diagnostic:visible").count(), 3);
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/ptk-log-analysis-light.png", fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 450, height: 900 });
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/ptk-log-analysis-dark.png", fullPage: true });
});

test("Sphinx needs charts, table, diagnostics and build links share the offline report", { skip: !python || !chromium ? "Requires PTK_TEST_PYTHON and Playwright" : false }, async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk needs report "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const code = "import sys; from pathlib import Path; from tests.reporting.test_sphinx import make_report; from ptk.adapters.reporting import html; root=Path(sys.argv[1]); (root/'report.html').write_text(html.render(make_report(root), link_root=root), encoding='utf-8')";
  const result = spawnSync(python, ["-c", code, root], { cwd: repo, encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repo, "src") }, timeout: 30000 });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const errors = [], requests = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route(/^https?:/, route => { requests.push(route.request().url()); return route.abort(); });
  await page.goto(require("node:url").pathToFileURL(path.join(root, "report.html")).href);
  const needs = page.locator("#needs"), table = page.locator("#needs-table");
  assert.equal(await needs.locator("details").first().evaluate(node => node.open), false);
  await needs.getByText("Needs charts and table", { exact: true }).click();
  assert.equal(await table.locator("tbody tr:visible").count(), 3);
  assert.equal(await needs.locator("svg circle").count(), 2);
  assert.equal(await needs.locator(".donut-total").textContent(), "3");
  await needs.locator('[data-need-field="type"][data-need-value="req"]').click();
  assert.equal(await table.locator("tbody tr:visible").count(), 2);
  await table.getByLabel("Need status", { exact: true }).selectOption("draft");
  assert.equal(await table.locator("tbody tr:visible").count(), 1);
  await table.getByRole("searchbox").fill("Backup");
  assert.equal(await table.locator("tbody tr:visible").count(), 1);
  await table.getByRole("button", { name: "Reset filters", exact: true }).click();
  await table.getByLabel("Need validation", { exact: true }).selectOption("error");
  assert.equal(await table.locator("tbody tr:visible").count(), 1);
  await table.locator("tbody tr:visible summary").click();
  assert.match(await table.locator("tbody tr:visible pre").textContent(), /"ASIL": "QM"/);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  await page.locator("#failures a").first().click();
  const target = page.locator(await page.evaluate(() => location.hash));
  assert.equal(await target.evaluate(node => node.open), true);
  assert.equal(await target.getAttribute("data-source"), "sphinx");
  await target.getByText("Nested validation details", { exact: true }).click();
  assert.match(await target.innerText(), /Nested reason/);
  await table.getByRole("button", { name: "Reset filters", exact: true }).click();
  await needs.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/ptk-needs-light.png", fullPage: false });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await needs.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/ptk-needs-dark.png", fullPage: false });
  await needs.locator(".docs-links a").click();
  assert.match(await page.locator("h1").textContent(), /Documentation/);
  assert.deepEqual(errors, []); assert.deepEqual(requests, []);
});

test("Bazel evidence shares offline diagnostics and searchable target/attempt views", { skip: !python || !chromium ? "Requires PTK_TEST_PYTHON and Playwright" : false }, async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk bazel report "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const code = `
import sys
from pathlib import Path
from ptk.domain.reporting.model import Report, BazelReport, LogFinding
from ptk.adapters.reporting.store import FileReportStore
root=Path(sys.argv[1]); (root/'test.log').write_text('Local test evidence')
r=Report('demo','build','debug','run','passed','',1,{}, {}, [])
b=BazelReport('test','build/events.bep.json',version='9.1.0',command='test',complete=True,status='passed')
b.diagnostics=[LogFinding('Bazel','R','error','<script>window.injected=true</script>',step='test',context=['Source: Bazel BEP action','Source: Bazel console']),LogFinding('Bazel','W','warning','Active warning',step='test'),LogFinding('Bazel','W','warning','Accepted warning',step='test',disposition='justified',reason='Reviewed upstream')]
b.targets=[{'label':'//:core','configuration':'cfg','status':'passed'},{'label':'//:app','configuration':'cfg','status':'failed'}]
b.tests=[{'label':'//:unit','configuration':'cfg','status':'FLAKY'}]
b.test_attempts=[{'label':'//:unit','configuration':'cfg','status':'PASSED','run':1,'shard':2,'attempt':3,'cached_locally':True}]
b.metrics={'actionSummary':{'actionsExecuted':'7'},'timingMetrics':{'wallTimeInMs':'1234'}}
b.artifacts=[{'name':'test.log','uri':(root/'test.log').as_uri()}]
r.bazel=[b]
FileReportStore({}).write(r,['html','json'],root)
`;
  const result = spawnSync(python, ["-c", code, root], { cwd: repo, encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repo, "src") }, timeout: 30000 });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [], requests = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route(/^https?:/, route => { requests.push(route.request().url()); return route.abort(); });
  await page.goto(require("node:url").pathToFileURL(path.join(root, "diagnostics.html")).href);
  const section = page.locator("#diagnostics");
  await section.getByLabel("Source", { exact: true }).selectOption("bazel");
  assert.equal(await section.locator(".diagnostic:visible").count(), 2);
  await section.getByLabel("Disposition", { exact: true }).selectOption("justified");
  assert.equal(await section.locator(".diagnostic:visible").count(), 1);
  await page.locator("#failures a").first().click();
  const selected = page.locator(await page.evaluate(() => location.hash));
  assert.equal(await selected.evaluate(node => node.open), true);
  assert.match(await selected.innerText(), /Bazel BEP action.*Bazel console/);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  await page.getByRole("link", { name: "Open full report", exact: true }).first().click();
  const bazel = page.locator("#bazel");
  assert.equal(await bazel.locator(":scope > details").evaluate(node => node.open), false);
  await bazel.locator(":scope > details > summary").click();
  const targets = bazel.locator('[data-filter="Bazel Targets"]');
  await targets.getByRole("searchbox").fill("//:app");
  assert.equal(await targets.locator("[data-record]:visible").count(), 1);
  assert.match(await bazel.locator('[data-filter="Bazel Test attempts, shards and runs"] summary').innerText(), /run 1 \/ shard 2 \/ attempt 3/);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  const artifact = bazel.locator('[data-filter="Bazel Artifact references"]');
  await artifact.locator("summary").click();
  await artifact.getByRole("link", { name: "Open local artifact" }).click();
  assert.match(await page.locator("body").innerText(), /Local test evidence/);
  assert.deepEqual(errors, []); assert.deepEqual(requests, []);
});

test("Dedicated diagnostics share sources, warning/disposition filters, escaped text and CMake graphs", { skip: !python || !chromium ? "Requires PTK_TEST_PYTHON and Playwright" : false }, async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ptk diagnostics report "));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const code = `
import sys
from pathlib import Path
from ptk.domain.reporting.model import Report, CMakeReport, LogFinding
from ptk.adapters.reporting.store import FileReportStore
r=Report('demo','build','debug','run','passed','',1,{}, {}, [])
c=CMakeReport('configure','build','4.1.3','cmake-4.1',status='passed')
c.diagnostics=[LogFinding('CMake','R','error','<script>window.injected=true</script>',step='configure',context=['Source: CMake SARIF','Source: CMake console']),LogFinding('CMake','W','warning','Active warning',step='configure'),LogFinding('CMake','W','warning','Accepted warning',step='configure',disposition='justified',reason='Reviewed upstream')]
c.targets=[{'id':'core','name':'core','type':'STATIC_LIBRARY','configuration':'Debug','needs':[]},{'id':'app','name':'app','type':'EXECUTABLE','configuration':'Debug','needs':['core']}]
r.cmake=[c]
FileReportStore({}).write(r,['html','json'],Path(sys.argv[1]))
`;
  const result = spawnSync(python, ["-c", code, root], { cwd: repo, encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repo, "src") }, timeout: 30000 });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_TEST_CHROMIUM, args: ["--no-sandbox"] });
  t.after(() => browser.close());
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [], requests = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route(/^https?:/, route => { requests.push(route.request().url()); return route.abort(); });
  await page.goto(require("node:url").pathToFileURL(path.join(root, "diagnostics.html")).href);
  const section = page.locator("#diagnostics");
  assert.equal(await section.locator(".diagnostic:visible").count(), 2);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  await section.getByLabel("Severity", { exact: true }).selectOption("warning");
  assert.equal(await section.locator(".diagnostic:visible").count(), 1);
  await section.getByLabel("Disposition", { exact: true }).selectOption("justified");
  const justified = section.locator(".diagnostic:visible");
  await justified.locator("summary").click();
  assert.match(await justified.innerText(), /Reviewed upstream/);
  await page.locator("#failures a").first().click();
  const selected = page.locator(await page.evaluate(() => location.hash));
  assert.equal(await selected.evaluate(node => node.open), true);
  assert.match(await selected.innerText(), /CMake SARIF.*CMake console/);
  await page.screenshot({ path: "/tmp/ptk-diagnostics-light.png", fullPage: false });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: "/tmp/ptk-diagnostics-dark.png", fullPage: false });
  await page.getByRole("link", { name: "Open full report", exact: true }).first().click();
  const cmake = page.locator("#cmake");
  await cmake.locator(":scope > details > summary").click();
  const graph = cmake.locator(".ptk-graph");
  assert.equal(await graph.evaluate(node => node.open), false);
  await graph.locator(":scope > summary").click();
  await page.waitForFunction(() => document.querySelector('#cmake .ptk-graph svg').getBoundingClientRect().height > 0);
  assert.equal(await graph.locator('[data-graph-action="fit"]').count(), 1);
  assert.match(await graph.locator('.ptk-graph-data').textContent(), /"needs": \["core"\]/);
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []); assert.deepEqual(requests, []);
});
