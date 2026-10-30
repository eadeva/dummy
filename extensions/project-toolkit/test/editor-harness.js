"use strict";
const { createEditors } = require("../src/editors");
const path = require("node:path");

function harness(text = "jobs: {}\n") {
  const listeners = new Set(), saves = new Set(), panels = [], executed = [], errors = [], edits = [];
  let provider, accepted = true, saved = true, changed = 0, validations = 0;
  const uri = fsPath => ({ fsPath, scheme: "file", toString() { return this.fsPath; } });
  const document = { uri: uri(path.resolve("example.ptk.yml")), version: 1, isDirty: false,
    getText: () => text, positionAt: offset => offset,
    async save() { if (!saved) return false; this.isDirty = false; for (const cb of saves) cb(this); return true; } };
  const disposable = () => ({ dispose() {} });
  const subscribe = (set, callback) => { set.add(callback); return { dispose: () => set.delete(callback) }; };
  function external(value) {
    text = value; document.version++; document.isDirty = true;
    for (const cb of listeners) cb({ document });
  }
  function panel() {
    const callbacks = new Set(), closed = new Set();
    const p = { messages: [], isDisposed: false, options: {}, revealed: false,
      webview: {
        cspSource: "http://ptk.test", asWebviewUri: uri => `http://ptk.test/${path.basename(uri.fsPath)}`,
        onDidReceiveMessage: callback => subscribe(callbacks, callback),
        postMessage: async message => { p.messages.push(message); await p.onPost?.(message); return true; },
      },
      receive: async message => { for (const cb of callbacks) await cb(message); },
      reveal() { p.revealed = true; },
      onDidDispose: callback => subscribe(closed, callback),
      dispose() { if (!p.isDisposed) { p.isDisposed = true; for (const cb of closed) cb(); } },
    };
    panels.push(p); return p;
  }
  const context = { extensionUri: uri(path.resolve(__dirname, "..")), subscriptions: [] };
  const api = {
    Uri: { file: uri, joinPath: (base, ...parts) => uri(path.join(base.fsPath, ...parts)) },
    ViewColumn: { Active: 1 },
    Range: class { constructor(start, end) { Object.assign(this, { start, end }); } },
    WorkspaceEdit: class { replace(uri, range, text) { this.change = { uri, range, text }; } },
    workspace: {
      isTrusted: true,
      openTextDocument: async () => document,
      onDidChangeTextDocument: callback => subscribe(listeners, callback),
      onDidSaveTextDocument: callback => subscribe(saves, callback),
      async applyEdit(edit) {
        edits.push(edit.change);
        if (!accepted) return false;
        const { range, text: inserted } = edit.change;
        external(text.slice(0, range.start) + inserted + text.slice(range.end));
        return true;
      },
    },
    window: {
      registerCustomEditorProvider: (_type, value) => { provider = value; return disposable(); },
      showErrorMessage: async error => errors.push(error),
      createWebviewPanel: (_type, _title, _column, options) => { const p = panel(); p.options = options; return p; },
    },
    commands: { executeCommand: async (...args) => executed.push(args) },
  };
  const editors = createEditors(api, context, { changed: () => changed++, validate: async () => validations++, configuration: () => ({ version: 3, schema: require("../media/config-schema.json"), documents: [{ file: document.uri.fsPath, schema: require("../media/config-schema.json") }] }) });
  return { api, context, document, editors, panels, executed, errors, edits, external,
    changeCount: () => changed, validationCount: () => validations,
    setAccepted: value => { accepted = value; }, setSaved: value => { saved = value; },
    async resolve() { const p = panel(); await provider.resolveCustomTextEditor(document, p); return p; },
  };
}
module.exports = { harness };
