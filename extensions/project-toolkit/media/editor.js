/* global acquireVsCodeApi, PtkSchema, PtkPresentation */
"use strict";
(() => {
  const vscode = acquireVsCodeApi();
  const S = PtkSchema;
  const P = PtkPresentation;
  const app = document.getElementById("app");
  let state, schema, selected = [], issue = "", serial = 0, inflight, commitRequested = false, rendering = false;
  const queue = new Map();
  let deferred;
  let parameterDraft = {};
  const stored = vscode.getState() || {};
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const display = value => typeof value === "string" ? value : JSON.stringify(value);
  const valueAt = path => path.reduce((value, key) => value?.[key], state.value);
  const fieldHelp = {
    help: "Description shown in the PTK tree, command help and parameter form.",
    open_report: "Choose when PTK opens the report after this job or workflow finishes.",
    params: "Named parameters accepted by this job. Add help, a type, choices or a default for each parameter.",
    steps: "Steps run in the order shown. Open an item to edit its name and settings.",
    run: "Command string or argument list. An argument list preserves spaces in each argument.",
    uses: "Registered plugin used to execute this step. Configure its inputs in with.",
    with: "Inputs passed to the selected plugin.",
    timeout: "Maximum time for this step in seconds.",
    retries: "Number of additional attempts after a failed step.",
    cwd: "Working directory for the step. PTK template expressions are supported.",
    env: "Environment settings. For a parameter, this names the environment variable used before its default.",
  };
  function el(tag, text, attrs = {}) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "className") node.className = value;
      else node.setAttribute(key, value);
    }
    return node;
  }
  function button(label, callback, className = "secondary") {
    const node = el("button", label, { type: "button", className });
    node.addEventListener("click", callback);
    return node;
  }
  function notice(container) {
    const node = el("div", issue, { className: "notice error", role: "alert", id: "issue" });
    node.hidden = !issue;
    container.append(node);
  }
  function showIssue(message) {
    issue = message || "";
    const node = document.getElementById("issue");
    if (node) { node.textContent = issue; node.hidden = !issue; }
  }
  function remember() {
    // Parameter values may be sensitive even if not declared secret. Keep them
    // only in the live webview, never in persisted VS Code webview state.
    if (state?.mode === "configuration") vscode.setState({ selected });
  }
  function status() {
    const node = document.getElementById("status");
    const validation = document.getElementById("validation-error");
    if (validation) { validation.textContent = state.validationError || ""; validation.hidden = !state.validationError; }
    if (node) node.textContent = inflight ? "Saving…" : queue.size ? "Editing · Leave the field or press Ctrl/Cmd+S to save" : state.dirty ? "Unsaved changes · Ctrl/Cmd+S to save" : "Saved";
  }
  function flush(request = true) {
    if (request) commitRequested = true;
    if (inflight || !state) return;
    if (!queue.size) {
      commitRequested = false;
      if (deferred) { const action = deferred; deferred = undefined; action(); }
      return;
    }
    if (commitRequested) {
      commitRequested = false;
      const operations = [...queue.values()];
      queue.clear();
      inflight = { id: ++serial, operations, structural: operations.some(op => op.render || op.op !== "set" || op.value !== null && typeof op.value === "object") };
      vscode.postMessage({ type: "edit", id: inflight.id, version: state.version, operations });
      status();
    }
  }
  function afterEdits(action) {
    const invalid = document.querySelector('[aria-invalid="true"]');
    if (invalid) { showIssue("Enter a valid number before continuing."); invalid.focus(); return; }
    document.activeElement?.blur();
    deferred = action;
    flush();
  }
  function change(operation, immediate = false) {
    queue.set(JSON.stringify(operation.path), operation);
    showIssue("");
    status();
    if (immediate) flush();
  }
  function navigate(path) {
    afterEdits(() => {
      selected = path;
      if (valueAt(selected) === null || typeof valueAt(selected) !== "object") selected = selected.slice(0, -1);
      remember(); renderConfiguration();
    });
  }
  function control(value, spec, onValue, id) {
    const resolved = S.effective(spec, value, schema);
    let input;
    if (resolved.enum) {
      input = el("select", undefined, { id });
      const values = resolved.enum.includes(value) ? resolved.enum : [value, ...resolved.enum];
      for (const option of values) input.append(el("option", String(option), { value: String(option) }));
      input.value = String(value);
      input.addEventListener("change", () => { onValue(resolved.enum.find(value => String(value) === input.value) ?? input.value); flush(); });
    } else if (typeof value === "boolean") {
      input = el("input", undefined, { type: "checkbox", id });
      input.checked = value;
      input.addEventListener("change", () => { onValue(input.checked); flush(); });
    } else if (value === null) {
      input = el("span", "null — choose a type below to set a value", { className: "muted", id });
    } else {
      const numeric = typeof value === "number";
      input = el(typeof value === "string" && value.includes("\n") ? "textarea" : "input", undefined, { id });
      if (input.tagName === "INPUT") input.type = numeric ? "number" : "text";
      if (numeric) {
        input.step = resolved.type === "integer" ? "1" : "any";
        if (resolved.minimum !== undefined) input.min = String(resolved.minimum);
        if (resolved.maximum !== undefined) input.max = String(resolved.maximum);
      }
      input.value = String(value);
      input.addEventListener("input", () => {
        if (numeric && (!input.value.trim() || !input.checkValidity() || !Number.isFinite(Number(input.value)))) {
          input.setAttribute("aria-invalid", "true"); return;
        }
        input.removeAttribute("aria-invalid");
        onValue(numeric ? Number(input.value) : input.value);
      });
      input.addEventListener("blur", () => { if (!rendering && !input.hasAttribute("aria-invalid")) flush(); });
    }
    return input;
  }
  function renderConfiguration() {
    rendering = true;
    try {
      const active = document.activeElement;
      const focus = active?.id ? { id: active.id, start: active.selectionStart, end: active.selectionEnd,
        value: active.value, invalid: active.getAttribute("aria-invalid"),
        draft: [...queue.values()].some(op => `field-${JSON.stringify(op.path)}` === active.id) } : undefined;
      const scroll = [window.scrollX, window.scrollY];
      app.replaceChildren();
      const header = el("header");
      const toolbar = el("div", undefined, { className: "toolbar" });
      const heading = el("div");
      heading.append(el("div", "PTk / Configuration", { className: "brand" }), el("h1", state.filename));
      const actions = el("div", undefined, { className: "actions" });
      actions.append(button("Raw YAML", () => afterEdits(() => vscode.postMessage({ type: "raw" }))),
        button("Save & validate", () => afterEdits(() => vscode.postMessage({ type: "validate" }))),
        button("Save", () => afterEdits(() => vscode.postMessage({ type: "save" })), ""));
      toolbar.append(heading, actions);
      header.append(toolbar, el("p", "", { className: "status", id: "status", role: "status" }));
      app.append(header);
      status();
      if (state.error) {
        const main = el("main"); notice(main);
        main.append(el("h2", "This YAML needs attention"), el("p", state.error, { className: "notice error" }), el("p", "Open Raw YAML to fix syntax errors, then switch back using Open PTK Form in the editor title bar."));
        app.append(main); return;
      }
      const layout = el("div", undefined, { className: "layout" });
      const main = el("main");
      notice(main);
      if (state.logical) {
        const validation = el("p", state.validationError || "", { className: "notice error", role: "alert", id: "validation-error" });
        validation.hidden = !state.validationError; main.append(validation);
      }
      while (selected.length && (valueAt(selected) === undefined || valueAt(selected) === null || typeof valueAt(selected) !== "object")) selected.pop();
      const crumbs = el("div", undefined, { className: "crumbs", "aria-label": "Field path" });
      crumbs.append(button("Configuration", () => navigate([]), "link"));
      selected.forEach((key, i) => {
        const path = selected.slice(0, i + 1);
        if (typeof key === "number" && P.namedEntry(valueAt(path), path) === selected[i + 1]) return;
        crumbs.append(el("span", "/"), button(P.pathLabel(state.value, path), () => navigate(path), "link"));
      });
      main.append(crumbs, el("h2", P.pathLabel(state.value, selected)));
      const value = valueAt(selected);
      const spec = S.at(schema, state.value, selected, schema);
      const resolved = S.effective(spec, value, schema);
      if (resolved.description) main.append(el("p", resolved.description, { className: "help" }));
      if (state.locked.some(prefix => prefix.length <= selected.length && prefix.every((key, i) => key === selected[i]))) {
        main.append(el("p", "This value uses an alias, unsupported tag or complex mapping. Use Raw YAML to edit it.", { className: "notice" }));
      } else if (value === null || typeof value !== "object") {
        main.append(el("p", "PTK configuration files must contain a mapping. Use Raw YAML to correct this document.", { className: "notice" }));
      } else {
        const entries = Object.entries(value);
        if (!entries.length) main.append(el("p", "No fields yet. Add a field below to get started.", { className: "empty" }));
        entries.forEach(([key, current]) => {
          const index = Array.isArray(value) ? Number(key) : key;
          renderField(main, [...selected, index], current, S.child(spec, value, index, schema), (resolved.required || []).includes(key), Array.isArray(value) ? value.length : undefined, !Array.isArray(value) && !resolved.properties?.[key] && resolved.additionalProperties !== false);
        });
        addField(main, value, spec, resolved);
      }
      layout.append(main); app.append(layout);
      if (focus) {
        const input = document.getElementById(focus.id);
        if (input) {
          if (focus.draft || focus.invalid) input.value = focus.value;
          if (focus.invalid) input.setAttribute("aria-invalid", focus.invalid);
          input.focus({ preventScroll: true });
          if (typeof focus.start === "number" && (["text", "search", "url", "tel", "password"].includes(input.type) || input.tagName === "TEXTAREA")) input.setSelectionRange(focus.start, focus.end);
        }
      }
      window.scrollTo(...scroll);
    } finally { rendering = false; }
  }
  function renderField(main, path, value, spec, required, listLength, canRename) {
    const key = path.at(-1);
    const id = `field-${JSON.stringify(path)}`;
    const resolved = S.effective(spec, value, schema);
    const field = el("section", undefined, { className: "field", "data-type": S.type(value) });
    const top = el("div", undefined, { className: "field-top" });
    const name = el("label", P.pathLabel(state.value, path), { className: "name", for: id });
    top.append(name, el("span", required ? "required" : S.type(value), { className: "badge" }));
    field.append(top);
    const help = resolved.description || fieldHelp[key];
    if (help) field.append(el("p", help, { className: "help" }));
    const tag = state.annotations.find(item => same(item.path, path));
    if (tag) field.append(el("p", `YAML tag: ${tag.text}`, { className: "help" }));
    const locked = state.locked.some(prefix => prefix.length <= path.length && prefix.every((key, i) => key === path[i]));
    if (locked) {
      field.append(el("p", `${display(value)} · Edit this value in Raw YAML.`, { className: "notice" }));
      main.append(field); return;
    }
    if (value !== null && typeof value === "object") {
      const summary = Array.isArray(value) ? `${value.length} items` : Object.keys(value).join(", ") || "Empty object";
      field.append(el("p", summary, { className: "help" }), button("Edit fields →", () => navigate(P.namedEntry(value, path) ? [...path, P.namedEntry(value, path)] : path)));
    } else {
      field.append(control(value, spec, next => change({ op: "set", path, value: next }), id));
    }
    const actions = el("div", undefined, { className: "field-actions" });
    let types = [...new Set(S.choices(spec, schema).map(item => item.type).filter(Boolean))];
    if (!types.length) types = ["string", "number", "boolean", "object", "array", "null"];
    if (types.length > 1) {
      const select = el("select", undefined, { "aria-label": `${key} value type` });
      for (const type of types) select.append(el("option", type, { value: type }));
      select.value = types.includes(S.type(value)) ? S.type(value) : types.includes("number") && typeof value === "number" ? "number" : types[0];
      select.addEventListener("change", () => {
        const next = S.choices(spec, schema).find(item => item.type === select.value) || { type: select.value };
        afterEdits(() => change({ op: "set", path, value: S.initial(next, schema), render: true }, true));
      });
      actions.append(select);
    }
    if (typeof key === "number") {
      const up = button("Move up", () => afterEdits(() => change({ op: "move", path, direction: -1 }, true)), "secondary small");
      const down = button("Move down", () => afterEdits(() => change({ op: "move", path, direction: 1 }, true)), "secondary small");
      up.disabled = key === 0; down.disabled = key === listLength - 1;
      actions.append(up, down);
    }
    if (canRename) {
      actions.append(button("Rename", () => {
        const row = el("div", undefined, { className: "row" });
        const input = el("input", undefined, { "aria-label": `New name for ${key}` });
        input.value = String(key);
        row.append(input, button("Apply name", () => afterEdits(() => change({ op: "rename", path, name: input.value.trim() }, true))));
        field.append(row); input.focus();
      }, "secondary small"));
    }
    actions.append(button("Remove", () => afterEdits(() => change({ op: "remove", path }, true)), "danger small"));
    field.append(actions); main.append(field);
  }
  function addField(main, value, spec, resolved) {
    const box = el("fieldset", undefined, { className: "add" });
    const isList = Array.isArray(value);
    const isJobs = selected.at(-1) === "jobs";
    box.append(el("legend", isJobs ? "Add a job" : isList ? "Add an item" : "Add a field"));
    const row = el("div", undefined, { className: "row" });
    let name, options = Object.keys(resolved.properties || {}).filter(key => !Object.hasOwn(value, key));
    if (!isList && resolved.additionalProperties === false) {
      if (!options.length) return;
      name = el("select", undefined, { "aria-label": "Optional field" });
      for (const key of options) name.append(el("option", key, { value: key }));
    } else if (!isList) name = el("input", undefined, { placeholder: isJobs ? "e.g. build" : "Field name", "aria-label": isJobs ? "New job name" : "New field name" });
    const help = el("p", "", { className: "help" });
    if (name) {
      row.append(name);
      const describe = () => {
        const field = resolved.properties?.[name.value] || {};
        help.textContent = field.description || fieldHelp[name.value] || (Object.hasOwn(field, "default") ? `Default: ${display(field.default)}` : "");
      };
      name.addEventListener("change", describe); describe();
    }
    row.append(button(isJobs ? "Add job" : isList ? "Add item" : "Add field", () => {
      const key = isList ? value.length : name.value.trim();
      if (!isList && (!key || ["__proto__", "constructor", "prototype"].includes(key))) { showIssue("Enter a valid field name."); return; }
      if (isJobs && !/^[a-z][a-z0-9-]*$/.test(key)) { showIssue("Job names must start with a lowercase letter and contain only lowercase letters, digits or hyphens."); return; }
      if (!isList && Object.hasOwn(value, key)) { showIssue(`Field ${key} already exists.`); return; }
      const child = S.child(spec, value, key, schema);
      let next = S.initial(child, schema);
      const directory = S.resolve(child, schema)["x-ptk-directory-template"];
      if (directory) next.path = directory.replace("{name}", key);
      if (isList && child.$ref === "#/$defs/StepEntry") next = { [`step_${key + 1}`]: { run: "echo Hello" } };
      afterEdits(() => change({ op: "add", path: [...selected, key], value: next }, true));
    }, ""));
    box.append(row, help); main.append(box);
  }
  function renderParameters() {
    app.replaceChildren();
    const header = el("header");
    header.append(el("div", "PTk / Job parameters", { className: "brand" }), el("h1", state.name), el("p", [state.project, state.variant && `Variant: ${state.variant}`].filter(Boolean).join(" · "), { className: "muted" }));
    app.append(header);
    const main = el("main", undefined, { className: "parameters" });
    notice(main);
    if (state.help) main.append(el("p", state.help));
    main.append(el("p", "Enable an override to supply a value. Otherwise PTK uses the configured environment or default when the job runs.", { className: "muted" }));
    const controls = [];
    for (const spec of state.params) {
      const id = `parameter-${spec.name}`;
      const field = el("section", undefined, { className: "field", "data-type": spec.type === "bool" ? "boolean" : "string" });
      const top = el("div", undefined, { className: "field-top" });
      top.append(el("label", spec.name, { className: "name", for: id }), el("span", `${spec.type}${spec.required ? " · required" : ""}`, { className: "badge" }));
      field.append(top);
      if (spec.help) field.append(el("p", spec.help, { className: "help", id: `${id}-help` }));
      if (spec.default !== undefined && spec.default !== null) field.append(el("p", `Default: ${display(spec.default)}${spec.default_is_template ? " (resolved when the job runs)" : ""}`, { className: "help" }));
      if (spec.env) field.append(el("p", `Environment: ${spec.env} (takes precedence over the default)`, { className: "help" }));
      if (spec.type === "list") field.append(el("p", "Separate list items with commas.", { className: "help" }));
      const cached = parameterDraft[spec.name];
      const required = spec.required && !spec.env;
      const override = el("input", undefined, { type: "checkbox", "aria-label": `Override ${spec.name}` });
      override.checked = cached ? cached.enabled : required;
      override.disabled = required;
      const label = el("label", undefined, { className: "check" });
      label.append(override, document.createTextNode(required ? "Value required" : "Override value"));
      field.append(label);
      let input;
      if (spec.type === "choice") {
        input = el("select", undefined, { id });
        for (const choice of spec.choices) input.append(el("option", choice, { value: choice }));
      } else input = el("input", undefined, { id, type: spec.type === "bool" ? "checkbox" : ["int", "float"].includes(spec.type) ? "number" : "text" });
      input.setAttribute("aria-describedby", `${id}-help`);
      if (["int", "float"].includes(spec.type)) input.step = spec.type === "int" ? "1" : "any";
      const defaultValue = spec.default_is_template ? "" : Array.isArray(spec.default) ? spec.default.join(", ") : spec.default;
      const value = cached?.value ?? defaultValue;
      if (spec.type === "bool") input.checked = value === true || value === "true";
      else if (value !== undefined && value !== null) input.value = String(value);
      input.disabled = !override.checked;
      const save = () => { showIssue(""); parameterDraft[spec.name] = { enabled: override.checked, value: spec.type === "bool" ? String(input.checked) : input.value }; };
      override.addEventListener("change", () => { input.disabled = !override.checked; save(); if (override.checked) input.focus(); });
      input.addEventListener("input", save);
      const wrapper = el("div", undefined, { className: "field-actions" });
      if (spec.type === "bool") {
        const boolLabel = el("label", undefined, { className: "check" });
        boolLabel.append(input, document.createTextNode("Enabled")); wrapper.append(boolLabel);
      } else wrapper.append(input);
      field.append(wrapper); main.append(field); controls.push({ spec, override, input });
    }
    if (!state.params.length) main.append(el("p", "This job has no non-secret parameters.", { className: "empty" }));
    app.append(main);
    const footer = el("footer", undefined, { className: "actions" });
    function submit(preview) {
      const params = Object.create(null);
      for (const { spec, override, input } of controls) {
        if (!override.checked) continue;
        if (!input.checkValidity() || spec.required && spec.type !== "bool" && !input.value.trim()) {
          showIssue(`${spec.name}: enter a valid ${spec.type} value.`); input.focus(); return;
        }
        params[spec.name] = spec.type === "bool" ? String(input.checked) : input.value;
      }
      showIssue("");
      vscode.postMessage({ type: "submit", preview, params });
    }
    footer.append(button("Cancel", () => vscode.postMessage({ type: "cancel" })),
      button("Dry run", () => submit(true), state.preview ? "" : "secondary"),
      button(state.reRun ? "Clean & re-run" : "Run job", () => submit(false), state.preview ? "secondary" : ""));
    app.append(footer);
  }
  window.addEventListener("message", event => {
    const message = event.data;
    if (message.type === "issue") { showIssue(message.issue); return; }
    if (message.type === "navigate") { navigate(message.selection || []); return; }
    if (message.type !== "state") return;
    if (message.schema) schema = message.schema;
    if (message.mode === "parameters") { state = message; renderParameters(); return; }
    const first = !state;
    if (message.reason && inflight) return;
    const own = inflight && message.ack === inflight.id || ["saved", "validated"].includes(message.reason);
    const structural = inflight?.structural;
    const submitted = inflight?.operations || [];
    if (!own && inflight && message.version === state.version) return;
    if (!own && (queue.size || inflight) || message.issue) {
      if (own && message.issue) {
        const drafts = [...queue.values()];
        queue.clear();
        for (const operation of [...submitted, ...drafts]) queue.set(JSON.stringify(operation.path), operation);
      }
      commitRequested = false; deferred = undefined;
      issue = message.issue || "The document changed outside this form. Review the refreshed fields before editing again.";
    } else if (message.issue === undefined) issue = "";
    inflight = undefined;
    state = message;
    // A structural acknowledgement can arrive while a different field is being
    // typed. Keep queued keystrokes visible until their own edit is acknowledged.
    for (const operation of queue.values()) {
      if (operation.op === "set") {
        const parent = operation.path.slice(0, -1).reduce((value, key) => value?.[key], state.value);
        if (parent && typeof parent === "object") parent[operation.path.at(-1)] = operation.value;
      }
    }
    if (first) {
      selected = message.selection?.length ? message.selection : stored.selected || [];
    }
    if (schema && (state.error || !own || structural || message.issue)) renderConfiguration();
    else status();
    flush(false);
  });
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && state?.mode === "configuration") {
      event.preventDefault(); afterEdits(() => vscode.postMessage({ type: "save" }));
    }
  });
  vscode.postMessage({ type: "ready" });
})();
