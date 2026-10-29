"use strict";

const path = require("node:path");
const crypto = require("node:crypto");
const model = require("./config-model");
const core = require("./core");
const { validateParameters } = require("./parameters");
const projectEdits = require("./project-edits");
const fs = require("node:fs/promises");
const viewType = "project-toolkit.configuration";

function createEditors(vscode, context, { changed = () => {}, validate = async () => {}, project: reloadProject, configuration = () => undefined } = {}) {
  const panels = new Map();
  const selections = new Map();
  const media = vscode.Uri.joinPath(context.extensionUri, "media");
  function trusted() {
    if (!vscode.workspace.isTrusted) throw new Error("Trust this workspace before editing or running PTK.");
  }
  function html(webview) {
    const nonce = crypto.randomBytes(18).toString("base64");
    const resource = name => webview.asWebviewUri(vscode.Uri.joinPath(media, name));
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';"><link rel="stylesheet" href="${resource("editor.css")}"><title>Project Toolkit</title></head><body><div id="app"></div><script nonce="${nonce}" src="${resource("schema.js")}"></script><script nonce="${nonce}" src="${resource("presentation.js")}"></script><script nonce="${nonce}" src="${resource("variables.js")}"></script><script nonce="${nonce}" src="${resource("editor.js")}"></script></body></html>`;
  }
  function configure(panel) {
    panel.webview.options = { enableScripts: true, localResourceRoots: [media] };
    panel.webview.html = html(panel.webview);
  }
  function configurationState(document) {
    const base = { mode: "configuration", filename: path.basename(document.uri.fsPath), version: document.version, dirty: document.isDirty };
    try { return { ...base, ...model.inspect(document.getText()) }; }
    catch (error) { return { ...base, error: error.message }; }
  }
  const provider = {
    async resolveCustomTextEditor(document, panel) {
      trusted();
      const key = document.uri.toString();
      panels.set(key, panel);
      let applying = false;
      let disposed = false;
      let configurationValue;
      let variables, pathBindings;
      let chain = Promise.resolve();
      const post = message => !disposed && panel.webview.postMessage(message);
      function state(extra = {}) { return post({ type: "state", ...configurationState(document), configurationValue, variables, pathBindings, ...extra }); }
      const updates = vscode.workspace.onDidChangeTextDocument(event => {
        if (event.document.uri.toString() !== key) return;
        if (!applying) state();
      });
      const saves = vscode.workspace.onDidSaveTextDocument(saved => { if (saved.uri.toString() === key) { changed(); state({ reason: "saved" }); } });
      const messages = panel.webview.onDidReceiveMessage(message => {
        // Serialize edits, save and raw-editor switches for this document.
        chain = chain.then(async () => {
          if (disposed || !message || typeof message !== "object") return;
          try {
            trusted();
            if (message.type === "ready") {
              const selection = selections.get(key) || [];
              selections.delete(key);
              const installed = await configuration(document.uri);
              if (!installed?.schema || installed.version !== 2) return state({ error: "No compatible PTK project schema is available. Open the project and refresh PTK, or use Raw YAML.", schema: {}, selection });
              const schema = projectEdits.schemaForFile(installed, document.uri.fsPath);
              configurationValue = installed.value;
              variables = installed.variables;
              pathBindings = projectEdits.bindingsForFile(installed, document.uri.fsPath);
              return state({ schema: schema || {}, ...(schema ? {} : { error: "This file is not part of PTK’s configuration layout. Use Raw YAML." }), selection });
            }
            if (message.type === "edit") {
              if (message.version !== document.version) throw new Error("The YAML changed outside this form. Your edit was not applied; review the refreshed fields and try again.");
              const before = document.getText();
              const after = model.edit(before, message.operations);
              if (before !== after) {
                const patch = model.minimalEdit(before, after);
                const edit = new vscode.WorkspaceEdit();
                edit.replace(document.uri, new vscode.Range(document.positionAt(patch.start), document.positionAt(patch.end)), patch.text);
                applying = true;
                let accepted;
                try { accepted = await vscode.workspace.applyEdit(edit); }
                finally { applying = false; }
                if (!accepted) throw new Error("VS Code could not apply the edit. Review the YAML and try again.");
              }
              return state({ ack: message.id });
            }
            if (message.type === "save" || message.type === "validate") {
              if (!await document.save()) throw new Error("The configuration could not be saved.");
              if (message.type === "validate") await validate(document.uri);
              return state({ reason: message.type === "save" ? "saved" : "validated" });
            }
            if (message.type === "raw") return vscode.commands.executeCommand("vscode.openWith", document.uri, "default");
          } catch (error) { await state({ ack: message.id, issue: error.message }); }
        }).catch(error => vscode.window.showErrorMessage(`Project Toolkit: ${error.message}`));
        return chain;
      });
      panel.onDidDispose(() => {
        disposed = true;
        if (panels.get(key) === panel) panels.delete(key);
        updates.dispose(); saves.dispose(); messages.dispose();
      });
      configure(panel);
    },
  };
  context.subscriptions.push(vscode.window.registerCustomEditorProvider(viewType, provider, {
    webviewOptions: { retainContextWhenHidden: true }, supportsMultipleEditorsPerDocument: false,
  }));

  async function open(uri, selection = []) {
    trusted();
    model.validatePath(selection);
    const key = uri.toString();
    const panel = panels.get(key);
    if (panel) {
      panel.reveal();
      await panel.webview.postMessage({ type: "navigate", selection });
    } else {
      selections.set(key, selection);
      await vscode.commands.executeCommand("vscode.openWith", uri, viewType);
    }
  }

  async function openProject(owner, selection = []) {
    trusted();
    const key = `project:${owner.project.entry_file}`;
    if (panels.has(key)) {
      panels.get(key).reveal();
      return panels.get(key).webview.postMessage({ type: "navigate", selection });
    }
    let config = owner.project.configuration;
    if (!config || config.version !== 2) throw new Error("The installed PTK does not support this configuration editor. Update PTK and the extension together.");
    const panel = vscode.window.createWebviewPanel(viewType, `${owner.project.alias}: Configuration`, vscode.ViewColumn.Active, { retainContextWhenHidden: true });
    panels.set(key, panel);
    let version = 1, chain = Promise.resolve(), disposed = false;
    const state = extra => panel.webview.postMessage({ type: "state", mode: "configuration", logical: true,
      filename: owner.project.alias, version, value: config.value, schema: config.schema,
      variables: config.variables,
      error: config.value === null ? config.error : undefined, validationError: config.error,
      locked: config.locked || [], annotations: [], dirty: false, ...extra });
    async function refresh(extra) {
      owner = await reloadProject(owner.project.entry_file);
      config = owner.project.configuration;
      version++;
      return state(extra);
    }
    const listener = panel.webview.onDidReceiveMessage(message => {
      chain = chain.then(async () => {
        if (disposed) return;
        try {
          trusted();
          if (message.type === "ready") return state({ selection });
          if (message.type === "save") return state({ reason: "saved" });
          if (message.type === "validate") { await validate(vscode.Uri.file(owner.project.entry_file)); return state({ reason: "validated" }); }
          if (message.type === "raw") {
            const selected = await vscode.window.showQuickPick(config.files.map(file => ({ label: path.relative(owner.root, file), file })), { placeHolder: "Open configuration source" });
            if (selected) return vscode.commands.executeCommand("vscode.openWith", vscode.Uri.file(selected.file), "default");
            return;
          }
          if (message.type !== "edit") return;
          if (message.version !== version) throw new Error("Configuration changed. Review the refreshed form before editing again.");
          const before = config;
          owner = await reloadProject(owner.project.entry_file, { publish: false });
          config = owner.project.configuration;
          if (JSON.stringify(before.fingerprints) !== JSON.stringify(config.fingerprints)) throw new Error("A source file changed. Review the refreshed configuration before editing again.");
          const documents = new Map(), texts = new Map();
          for (const file of config.files) {
            const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
            if (doc.isDirty) throw new Error("Save or undo unsaved YAML edits before editing the project form.");
            if (config.fingerprints?.[file] && crypto.createHash("sha256").update(doc.getText()).digest("hex") !== config.fingerprints[file]) throw new Error("A source changed while loading. Refresh and retry the edit.");
            documents.set(file, doc); texts.set(file, doc.getText());
          }
          const changes = projectEdits.plan({ ...config, entry_file: owner.project.entry_file }, texts, message.operations);
          for (const [file, after] of changes) {
            const relative = path.relative(owner.root, file);
            if (relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) throw new Error("Configuration files must stay inside the repository.");
            for (let current = file; current !== owner.root; current = path.dirname(current)) {
              const stat = await fs.lstat(current).catch(error => { if (error.code !== "ENOENT") throw error; });
              if (stat?.isSymbolicLink()) throw new Error("Configuration paths cannot contain symbolic links.");
              if (current === file && stat && !documents.has(file)) throw new Error("The destination file already exists. Refresh PTK before editing it.");
            }
            if (after !== null && !documents.has(file)) await vscode.workspace.fs.createDirectory(vscode.Uri.file(path.dirname(file)));
          }
          const edit = new vscode.WorkspaceEdit();
          for (const [file, after] of changes) {
            const uri = vscode.Uri.file(file), doc = documents.get(file);
            if (after === null) { edit.deleteFile(uri); continue; }
            if (!doc) { edit.createFile(uri, { overwrite: false }); edit.insert(uri, new vscode.Position(0, 0), after); }
            else {
              const patch = model.minimalEdit(doc.getText(), after);
              edit.replace(uri, new vscode.Range(doc.positionAt(patch.start), doc.positionAt(patch.end)), patch.text);
            }
          }
          if (!await vscode.workspace.applyEdit(edit)) throw new Error("VS Code could not apply the configuration edit.");
          for (const [file, after] of changes) {
            if (after === null) continue;
            const doc = documents.get(file) || await vscode.workspace.openTextDocument(vscode.Uri.file(file));
            if (!await doc.save()) throw new Error("A configuration file could not be saved. Review the open YAML documents.");
          }
          return refresh({ ack: message.id });
        } catch (error) {
          version++;
          return state({ ack: message.id, issue: error.message });
        }
      }).catch(error => vscode.window.showErrorMessage(`Project Toolkit: ${error.message}`));
      return chain;
    });
    panel.onDidDispose(() => { disposed = true; panels.delete(key); listener.dispose(); });
    context.subscriptions.push(panel);
    configure(panel);
  }

  function parameters(target, options) {
    trusted();
    return new Promise(resolve => {
      const panel = vscode.window.createWebviewPanel("project-toolkit.parameters", `${options.preview ? "Dry run" : "Run"}: ${target.name}`, vscode.ViewColumn.Active, { retainContextWhenHidden: true });
      let settled = false;
      const finish = value => { if (!settled) { settled = true; resolve(value); panel.dispose(); } };
      const listener = panel.webview.onDidReceiveMessage(async message => {
        if (settled || !message || typeof message !== "object") return;
        try {
          trusted();
          if (message.type === "ready") return panel.webview.postMessage({ type: "state", mode: "parameters", name: target.name,
            kind: target.kind, project: target.project?.alias, help: target.spec.help,
            variantChoices: (target.project?.variants || []).filter(item => !item.abstract),
            defaultVariant: target.project?.default_variant, variantHelp: target.project?.variant_help, useDefault: options.useDefault,
            runOptions: target.spec.run_options || [], params: (target.spec.params || []).filter(spec => spec.type !== "secret"),
            preview: options.preview, variant: options.variant, variants: options.variants, reRun: !!options.reRun });
          if (message.type === "cancel") return finish();
          if (message.type === "submit") {
            if (typeof message.preview !== "boolean") throw new Error("Invalid run action.");
            validateParameters(target.spec.params || [], message.params);
            const runOptions = message.runOptions || {};
            core.builtinArgs({ params: target.spec.run_options || [] }, runOptions);
            if (runOptions.show_env?.[0] === "true" && !message.preview) throw new Error("Include environment requires Dry run.");
            const variants = message.variants || [];
            if (!Array.isArray(variants) || variants.some(name => !target.project?.variants.some(item => item.name === name && !item.abstract)) ||
                new Set(variants).size !== variants.length || target.kind === "workflow" && variants.length > 1) throw new Error("Choose available variants.");
            if (!variants.length && target.project?.variants.some(item => !item.abstract) && !target.project.default_variant) throw new Error("Select a variant; this project has no default.");
            finish({ params: message.params, preview: message.preview, runOptions, variants });
          }
        } catch (error) { await panel.webview.postMessage({ type: "issue", issue: error.message }); }
      });
      panel.onDidDispose(() => { listener.dispose(); if (!settled) { settled = true; resolve(); } });
      context.subscriptions.push(panel);
      configure(panel);
    });
  }
  return { open, openProject, parameters };
}

module.exports = { createEditors, viewType };
