/* Browser exercises the shipped webview assets against the real editor message handler. */
"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { harness } = require("../extensions/project-toolkit/test/editor-harness");
const YAML = require("../extensions/project-toolkit/node_modules/yaml");
const media = path.resolve(__dirname, "../extensions/project-toolkit/media");
const theme = `:root{--vscode-foreground:#d4d7df;--vscode-editor-background:#181c24;--vscode-font-family:system-ui;--vscode-font-size:13px;--vscode-descriptionForeground:#9ca7bc;--vscode-input-background:#242b38;--vscode-input-foreground:#e7eaf0;--vscode-input-border:#424c60;--vscode-panel-border:#343c4c;--vscode-focusBorder:#9b8afa;--vscode-charts-purple:#b29dff;--vscode-charts-blue:#6db5f6;--vscode-charts-green:#76c9a3;--vscode-charts-orange:#e5b66f;--vscode-button-background:#7361ce;--vscode-button-foreground:#fff;--vscode-button-hoverBackground:#8673e3;--vscode-button-secondaryBackground:#2b3342;--vscode-button-secondaryForeground:#e7eaf0;--vscode-textLink-foreground:#b4a4ff;--vscode-errorForeground:#ff9b9b;--vscode-badge-background:#29303d;--vscode-sideBar-background:#1d222c;--vscode-list-activeSelectionBackground:#36304e;--vscode-list-activeSelectionForeground:#fff}`;
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PTK_CHROMIUM, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  try {
    const errors = [];
    async function connect(panel) {
      const page = await browser.newPage({ viewport: { width: 1150, height: 900 } });
      page.on("pageerror", error => errors.push(error.message));
      await page.route("http://ptk.test/**", async route => {
        const name = new URL(route.request().url()).pathname.slice(1);
        if (name === "index.html") return route.fulfill({ contentType: "text/html", body: panel.webview.html });
        const body = await fs.readFile(path.join(media, name));
        return route.fulfill({ contentType: name.endsWith("css") ? "text/css" : "application/javascript", body: name.endsWith("css") ? Buffer.concat([Buffer.from(theme), body]) : body });
      });
      await page.exposeFunction("ptkHost", message => panel.receive(message));
      await page.addInitScript(() => {
        let stored;
        window.acquireVsCodeApi = () => ({ postMessage: message => window.ptkHost(message), getState: () => stored, setState: value => { stored = value; } });
      });
      panel.onPost = message => page.evaluate(data => window.dispatchEvent(new MessageEvent("message", { data })), message);
      await page.goto("http://ptk.test/index.html");
      return page;
    }
    const original = "# User comment\nproject:\n  name: example\njobs:\n  build:\n    help: Build the project\n    params:\n      verbose: {type: bool, default: false}\n    steps:\n      - compile: {run: echo hello}\n";
    const h = harness(original);
    const panel = await h.resolve();
    const page = await connect(panel);
    await page.getByRole("heading", { name: "Configuration", exact: true }).waitFor();
    await page.getByRole("button", { name: "jobs", exact: true }).click();
    await page.getByRole("textbox", { name: "New job name", exact: true }).fill("verify");
    await page.getByRole("button", { name: "Add job", exact: true }).click();
    await page.locator("section.field").filter({ has: page.getByText("verify", { exact: true }) }).waitFor();
    assert.ok(YAML.parse(h.document.getText()).jobs.verify.steps[0].step.run);
    const build = page.locator("section.field").filter({ has: page.getByText("build", { exact: true }) });
    await build.getByRole("button", { name: "Edit fields" }).click();
    await page.getByRole("combobox", { name: "Optional field", exact: true }).selectOption("open_report");
    await page.getByRole("button", { name: "Add field", exact: true }).click();
    await page.getByLabel("open_report", { exact: true }).selectOption("on_errors");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.getByText("Saved", { exact: true }).waitFor();
    assert.equal(YAML.parse(h.document.getText()).jobs.build.open_report, "on_errors");
    await page.getByLabel("help", { exact: true }).fill("Changed <script>alert(1)</script>");
    // Switching immediately must flush the last keystroke before opening YAML.
    await page.getByRole("button", { name: "Raw YAML", exact: true }).click();
    await page.waitForFunction(() => document.getElementById("status").textContent.includes("Unsaved"));
    assert.ok(h.document.getText().includes("Changed <script>alert(1)</script>"));
    assert.equal(h.executed.at(-1)[2], "default");
    assert.ok(h.document.getText().includes("# User comment"));
    await h.editors.open(h.document.uri, ["jobs", "build"]);
    await page.getByRole("heading", { name: "build", exact: true }).waitFor();
    // Raw changes and undo flow back through TextDocument events.
    h.external(original);
    await page.getByLabel("help", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("help", { exact: true }).inputValue(), "Build the project");
    if (process.env.PTK_UI_SCREENSHOTS) await page.screenshot({ path: path.join(process.env.PTK_UI_SCREENSHOTS, "configuration.png"), fullPage: true });
    await page.setViewportSize({ width: 420, height: 850 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.close();

    const params = [
      { name: "output", type: "path", required: true, help: "Folder for the build output" },
      { name: "verbose", type: "bool", default: true, help: "Include diagnostic output" },
      { name: "mode", type: "choice", choices: ["debug", "release"], default: "debug", help: "Build profile" },
      { name: "count", type: "int", default: 4, help: "Number of workers" },
      { name: "dynamic", type: "str", default: "${env:OUTPUT}", default_is_template: true, env: "OUTPUT" },
    ];
    const result = h.editors.parameters({ name: "build", project: { alias: "example" }, spec: { params, help: "Build the selected project" } }, { preview: false, variant: "debug" });
    const parameterPanel = h.panels.at(-1);
    const p = await connect(parameterPanel);
    await p.getByRole("heading", { name: "build", exact: true }).waitFor();
    await p.getByRole("button", { name: "Run job", exact: true }).click();
    assert.equal(parameterPanel.isDisposed, false);
    await p.getByText("output: enter a valid path value.", { exact: true }).waitFor();
    await p.getByLabel("output", { exact: true }).fill("folder with spaces;$(literal)");
    await p.getByRole("checkbox", { name: "Override verbose", exact: true }).check();
    await p.getByLabel("verbose", { exact: true }).uncheck();
    await p.getByRole("checkbox", { name: "Override mode", exact: true }).check();
    await p.getByLabel("mode", { exact: true }).selectOption("release");
    assert.equal(await p.getByLabel("dynamic", { exact: true }).isDisabled(), true);
    await p.getByText("Default: ${env:OUTPUT} (resolved when the job runs)", { exact: true }).waitFor();
    if (process.env.PTK_UI_SCREENSHOTS) await p.screenshot({ path: path.join(process.env.PTK_UI_SCREENSHOTS, "parameters.png"), fullPage: true });
    await p.getByRole("button", { name: "Dry run", exact: true }).click();
    assert.deepEqual(await result, { preview: true, params: { output: "folder with spaces;$(literal)", verbose: "false", mode: "release" } });
    assert.deepEqual(errors, []);
    console.log("Extension webviews: add job/model fields, preserve comments, edit/save/raw/undo, narrow layout, parameter defaults/choices/checkboxes/literal values and dry run passed.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
