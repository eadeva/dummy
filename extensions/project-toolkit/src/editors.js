"use strict";

const path = require("node:path");
const crypto = require("node:crypto");
const model = require("./config-model");
const { validateParameters } = require("./parameters");
const schema = require("../media/config-schema.json");
const viewType = "project-toolkit.configuration";

function createEditors(vscode, context, { changed = () => {}, validate = async () => {} } = {}) {
  const panels = new Map();
  const selections = new Map();
  const media = vscode.Uri.joinPath(context.extensionUri, "media");
  function trusted() {
    if (!vscode.workspace.isTrusted) throw new Error("Trust this workspace before editing or running PTK.");
  }
  function html(webview) {
    const nonce = crypto.randomBytes(18).toString("base64");
    const resource = name => webview.asWebviewUri(vscode.Uri.joinPath(media, name));
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}';"><link rel="stylesheet" href="${resource("editor.css")}"><title>Project Toolkit</title></head><body><div id="app"></div><script nonce="${nonce}" src="${resource("schema.js")}"></script><script nonce="${nonce}" src="${resource("editor.js")}"></script></body></html>`;
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
      let chain = Promise.resolve();
      const post = message => !disposed && panel.webview.postMessage(message);
      function state(extra = {}) { return post({ type: "state", ...configurationState(document), ...extra }); }
      const updates = vscode.workspace.onDidChangeTextDocument(event => {
        if (event.document.uri.toString() !== key) return;
        changed();
        if (!applying) state();
      });
      const saves = vscode.workspace.onDidSaveTextDocument(saved => { if (saved.uri.toString() === key) state(); });
      const messages = panel.webview.onDidReceiveMessage(message => {
        // Serialize edits, save and raw-editor switches for this document.
        chain = chain.then(async () => {
          if (disposed || !message || typeof message !== "object") return;
          try {
            trusted();
            if (message.type === "ready") {
              const selection = selections.get(key) || [];
              selections.delete(key);
              return state({ schema, selection });
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
              return state();
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

  async function children(element) {
    try {
      const document = await vscode.workspace.openTextDocument(vscode.Uri.file(element.configFile));
      const state = model.inspect(document.getText());
      const at = element.configPath || [];
      const value = at.reduce((value, key) => value?.[key], state.value);
      if (state.locked.some(prefix => prefix.length <= at.length && prefix.every((key, i) => key === at[i]))) return [];
      if (!value || typeof value !== "object") return [];
      return Object.entries(value).map(([name, value]) => {
        const key = Array.isArray(at.reduce((value, key) => value?.[key], state.value)) ? Number(name) : name;
        const configPath = [...at, key];
        const hasChildren = value !== null && typeof value === "object";
        const node = { ...element, configPath, kind: "config-field", label: typeof key === "number" ? `Item ${key + 1}` : name,
          id: JSON.stringify([element.configOwner, element.configFile, configPath]), collapsed: true, hasChildren,
          description: hasChildren ? Array.isArray(value) ? `${value.length} items` : `${Object.keys(value).length} fields` : value === null ? "null" : String(value).slice(0, 100),
          icon: hasChildren ? "symbol-namespace" : "symbol-property", children: undefined,
        };
        node.command = { command: "project-toolkit.openConfig", title: "Edit configuration field", arguments: [node] };
        return node;
      });
    } catch (error) {
      return [{ label: "Open Raw YAML to fix this file", description: error.message.split("\n")[0], icon: "warning",
        command: { command: "vscode.openWith", title: "Open Raw YAML", arguments: [vscode.Uri.file(element.configFile), "default"] } }];
    }
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
            project: target.project?.alias, help: target.spec.help, params: (target.spec.params || []).filter(spec => spec.type !== "secret"),
            preview: options.preview, variant: options.variant, reRun: !!options.reRun });
          if (message.type === "cancel") return finish();
          if (message.type === "submit") {
            if (typeof message.preview !== "boolean") throw new Error("Invalid run action.");
            validateParameters(target.spec.params || [], message.params);
            finish({ params: message.params, preview: message.preview });
          }
        } catch (error) { await panel.webview.postMessage({ type: "issue", issue: error.message }); }
      });
      panel.onDidDispose(() => { listener.dispose(); if (!settled) { settled = true; resolve(); } });
      context.subscriptions.push(panel);
      configure(panel);
    });
  }
  return { open, children, parameters };
}

module.exports = { createEditors, viewType };
