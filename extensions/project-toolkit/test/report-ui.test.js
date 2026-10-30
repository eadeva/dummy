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
  const section = page.locator(".log-analysis");
  assert.equal(await page.evaluate(() => window.injected), undefined);
  assert.equal(await section.getByLabel("Disposition", { exact: true }).inputValue(), "active");
  assert.equal(await section.locator("tbody tr:visible").count(), 3);
  assert.match(await section.locator(".log-status").innerText(), /^4 occurrences in 3/);
  assert.equal(await section.locator('[data-card="error"] strong').innerText(), "2");
  assert.equal(await section.locator('[data-card="warning"] strong').innerText(), "2");
  await section.getByLabel("Severity", { exact: true }).selectOption("warning");
  assert.equal(await section.locator("tbody tr:visible").count(), 1);
  await section.getByRole("button", { name: "Show justified", exact: true }).click();
  assert.equal(await section.getByLabel("Severity", { exact: true }).inputValue(), "");
  assert.equal(await section.getByLabel("Disposition", { exact: true }).inputValue(), "justified");
  const row = section.locator("tbody tr:visible");
  await row.locator("summary").click();
  assert.match(await row.innerText(), /Upgrade planned <next>/);
  assert.equal(await row.locator("mark").count(), 1);
  const href = await row.getByRole("link", { name: "compile.log" }).getAttribute("href");
  assert.equal(fs.existsSync(path.resolve(root, "_reports/default/build", decodeURIComponent(href))), true);
  await section.getByRole("button", { name: "Show ignored", exact: true }).click();
  assert.equal(await section.locator("tbody tr:visible").count(), 1);
  await section.getByLabel("Disposition", { exact: true }).selectOption("");
  assert.equal(await section.locator("tbody tr:visible").count(), 5);
  await section.getByRole("searchbox").fill("motor_start");
  assert.equal(await section.locator("tbody tr:visible").count(), 1);
  await section.getByRole("button", { name: "Reset filters", exact: true }).click();
  assert.equal(await section.locator("tbody tr:visible").count(), 3);
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/ptk-log-analysis-light.png", fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.setViewportSize({ width: 450, height: 900 });
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/ptk-log-analysis-dark.png", fullPage: true });
});
