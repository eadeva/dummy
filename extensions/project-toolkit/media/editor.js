/* global acquireVsCodeApi, PtkSchema, PtkPresentation, PtkVariables, PtkDependencies, PtkGraphEditor, PtkCreation */
"use strict";
(() => {
  const vscode = acquireVsCodeApi();
  const S = PtkSchema;
  const P = PtkPresentation;
  const app = document.getElementById("app");
  let state, schema, selected = [], issue = "", serial = 0, inflight, commitRequested = false, rendering = false;
  const queue = new Map();
  const deferred = [], uiDrafts = new Map();
  const expandedHelp = new Set();
  let pointerActive = false, renderPending = false;
  let variablePicker;
  let disposeGraph;
  let creation;
  const graphViews = new Map();
  let parameterDraft = {};
  const stored = vscode.getState() || {};
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const display = value => typeof value === "string" ? value : JSON.stringify(value);
  const valueAt = path => path.reduce((value, key) => value?.[key], state.value);
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
    if (node) node.textContent = creation ? creation.submitting ? "Creating…" : "Setup draft · Review and Create to add this element" : inflight || deferred.length ? "Saving…" : queue.size ? "Editing · Leave the field or press Ctrl/Cmd+S to save" : state.dirty ? "Unsaved changes · Ctrl/Cmd+S to save" : "Saved";
  }
  function flush(request = true) {
    if (request) commitRequested = true;
    if (inflight || !state) return;
    if (!queue.size) {
      commitRequested = false;
      if (deferred.length) {
        try { deferred.shift()(); }
        catch (error) { deferred.length = 0; showIssue(error.message); }
        if (!inflight && !queue.size && deferred.length) flush(false);
      }
      status();
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
    variablePicker?.close();
    const invalid = document.querySelector('[data-number-invalid="true"]');
    if (invalid) { showIssue("Enter a valid number before continuing."); invalid.focus(); return; }
    document.activeElement?.blur();
    deferred.push(action);
    flush();
  }
  function change(operation, immediate = false) {
    queue.set(JSON.stringify(operation.path), operation);
    showIssue("");
    status();
    if (immediate) flush();
  }
  function navigate(path) {
    if (creation) { showIssue("Finish or cancel setup before opening another field."); return; }
    afterEdits(() => {
      selected = path;
      if (valueAt(selected) === null || typeof valueAt(selected) !== "object") selected = selected.slice(0, -1);
      remember(); renderConfiguration();
    });
  }
  function control(value, spec, onValue, id, path) {
    const resolved = S.effective(spec, value, schema);
    let input;
    if (typeof value === "string" && resolved["x-ptk-reference"]) {
      const reference = resolved["x-ptk-reference"];
      const configuration = state.logical ? state.value : state.configurationValue;
      const graph = path && PtkDependencies.context(schema, state.value, path, S);
      const names = graph?.kind === "job" && path.at(-1) === "job"
        ? PtkDependencies.availableJobs(configuration, graph.value, graph.selected)
        : Object.keys(reference.path.reduce((value, key) => value?.[key], configuration) || {});
      if (reference["allow-custom"]) {
        input = el("input", undefined, { id, type: "text", list: `${id}-choices` });
        input.value = value;
        const list = el("datalist", undefined, { id: `${id}-choices` });
        names.forEach(name => list.append(el("option", name, { value: name })));
        (creation?.api.node || app).append(list);
        input.addEventListener("input", () => onValue(input.value));
        input.addEventListener("blur", () => { if (!rendering) flush(); });
      } else {
        input = el("select", undefined, { id });
        for (const name of new Set([value, ...names])) input.append(el("option", name, { value: name }));
        input.value = value;
        input.addEventListener("change", () => { onValue(input.value); flush(); });
      }
    } else if (resolved.enum) {
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
          input.setAttribute("aria-invalid", "true"); input.setAttribute("data-number-invalid", "true"); return;
        }
        input.removeAttribute("aria-invalid");
        input.removeAttribute("data-number-invalid");
        onValue(numeric ? Number(input.value) : input.value);
      });
      input.addEventListener("blur", event => {
        if (!rendering && !input.hasAttribute("data-number-invalid") && variablePicker?.input !== input && !event.relatedTarget?.closest(".variable-tools")) flush();
      });
    }
    return input;
  }
  function renderConfiguration() {
    // Keep the target button alive through pointerup/click if a save reply
    // arrives mid-click. Replacing it here silently loses the user's action.
    if (pointerActive || variablePicker) { renderPending = true; return; }
    renderPending = false;
    rendering = true;
    try {
      const active = document.activeElement;
      const focus = active?.id ? { id: active.id, start: active.selectionStart, end: active.selectionEnd,
        value: active.value, invalid: active.getAttribute("aria-invalid"), numberInvalid: active.getAttribute("data-number-invalid"),
        draft: active.hasAttribute("data-ui-draft") || [...queue.values()].some(op => `field-${JSON.stringify(op.path)}` === active.id) } : undefined;
      const scroll = [window.scrollX, window.scrollY];
      disposeGraph?.(); disposeGraph = undefined;
      app.replaceChildren();
      app.className = "configuration";
      const header = el("header");
      const toolbar = el("div", undefined, { className: "toolbar" });
      const heading = el("div");
      heading.append(el("div", "PTk / Configuration", { className: "brand" }), el("h1", state.filename));
      const actions = el("div", undefined, { className: "actions" });
      if (!creation) actions.append(button("Raw YAML", () => afterEdits(() => vscode.postMessage({ type: "raw" }))),
        button("Save & validate", () => afterEdits(() => vscode.postMessage({ type: "validate" }))),
        button("Save", () => afterEdits(() => vscode.postMessage({ type: "save" })), ""));
      toolbar.append(heading, actions);
      header.append(toolbar, el("p", "", { className: "status", id: "status", role: "status" }));
      app.append(header);
      status();
      if (state.error && !creation) {
        const main = el("main"); notice(main);
        main.append(el("h2", "This YAML needs attention"), el("p", state.error, { className: "notice error" }), el("p", "Open Raw YAML to fix syntax errors, then switch back using Open PTK Form in the editor title bar."));
        app.append(main); return;
      }
      if (creation) {
        const main = el("main"); notice(main);
        if (state.error) main.append(el("p", `The source YAML needs repair: ${state.error}. Cancel setup to open Raw YAML.`, { className: "notice error", role: "alert" }));
        main.append(creation.api.node); app.append(main);
        if (focus) {
          const input = document.getElementById(focus.id);
          input?.focus({ preventScroll: true });
          if (input?.setSelectionRange && focus.start !== null) { try { input.setSelectionRange(focus.start, focus.end); } catch {} }
        }
        if (creation.needsFocus) { creation.needsFocus = false; creation.api.node.querySelector("input, select, button")?.focus(); }
        return;
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
        crumbs.append(el("span", "/"), button(P.pathLabel(state.value, path), () => navigate(path), "link"));
      });
      main.append(crumbs, el("h2", P.pathLabel(state.value, selected), { "data-entity": P.entity(selected, state) || "" }));
      const graph = PtkDependencies.context(schema, state.value, selected, S);
      if (graph) {
        graph.owner = (state.logical ? state.value : state.configurationValue)?.repository?.alias;
        const canvas = el("div"); main.append(canvas);
        const locked = id => {
          const path = [...graph.path, id, "needs"];
          return state.locked.some(prefix => prefix.every((key, i) => path[i] === key) || path.every((key, i) => prefix[i] === key));
        };
        try {
          disposeGraph = PtkGraphEditor.mount(canvas, graph, {
            navigate,
            locked,
            create: defaults => startCreation(graph.path, defaults),
            refresh: renderConfiguration,
            view: graphViews.get(JSON.stringify(graph.path)) || (() => { const view = {}; graphViews.set(JSON.stringify(graph.path), view); return view; })(),
            connect: (from, to, remove) => afterEdits(() => {
              // Recheck after any queued field save before applying the edge edit.
              PtkDependencies.update(valueAt(graph.path), from, to, remove);
              change({ op: "dependency", path: [...graph.path, to], prerequisite: from, remove }, true);
            }),
          });
        } catch (error) {
          canvas.replaceChildren(el("p", `Graph could not be displayed: ${error.message}. Configuration fields remain available below.`, { className: "notice error", role: "alert" }));
        }
      }
      const value = valueAt(selected);
      const spec = S.at(schema, state.value, selected, schema);
      const resolved = S.effective(spec, value, schema);
      if (resolved.description) main.append(el("p", resolved.description, { className: "help" }));
      if (resolved.properties?.outputs && resolved.properties?.cache) {
        main.append(el("p", "Outputs primarily describe artifacts for uploads and downloads in workflows. Declaring outputs does not transfer files. PTK’s built-in cache is an optional aid: the project owns the output declarations and cache correctness. Reuse requires cache: true and explicit outputs; --no-cache-ptk disables it for the whole invocation.", { className: "help", "data-output-guidance": "true" }));
      }
      if (state.locked.some(prefix => prefix.length <= selected.length && prefix.every((key, i) => key === selected[i]))) {
        main.append(el("p", "This value uses an alias, unsupported tag or complex mapping. Use Raw YAML to edit it.", { className: "notice" }));
      } else if (value === null || typeof value !== "object") {
        main.append(el("p", "PTK configuration files must contain a mapping. Use Raw YAML to correct this document.", { className: "notice" }));
      } else {
        const entries = S.orderedEntries(spec, value, schema);
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
          if (focus.numberInvalid) input.setAttribute("data-number-invalid", focus.numberInvalid);
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
    const field = el("section", undefined, { className: "field", "data-type": S.type(value), "data-entity": P.entity(path, state) || "" });
    const top = el("div", undefined, { className: "field-top" });
    const name = el("label", P.pathLabel(state.value, path), { className: "name", for: id });
    top.append(name);
    if (required) top.append(el("span", "*", { className: "required-mark", title: "Required", "aria-label": "required" }));
    field.append(top);
    const help = S.help(spec, value, schema);
    const helpId = `${id}-help`;
    if (help) {
      const details = el("div", undefined, { className: "field-help", id: helpId });
      details.hidden = !expandedHelp.has(id);
      details.append(el("p", help, { className: "help" }));
      const toggle = button("?", () => {
        details.hidden = !details.hidden;
        if (details.hidden) expandedHelp.delete(id); else expandedHelp.add(id);
        toggle.setAttribute("aria-expanded", String(!details.hidden));
      }, "help-toggle");
      toggle.setAttribute("aria-label", `Help for ${name.textContent}`);
      toggle.setAttribute("aria-expanded", String(!details.hidden));
      toggle.setAttribute("aria-controls", helpId);
      toggle.title = resolved.description || help;
      name.title = toggle.title;
      top.append(toggle); field.append(details);
    }
    const body = el("div", undefined, { className: "field-value" });
    field.append(body);
    const tag = state.annotations.find(item => same(item.path, path));
    if (tag) body.append(el("p", `YAML tag: ${tag.text}`, { className: "help" }));
    const locked = state.locked.some(prefix => prefix.length <= path.length && prefix.every((key, i) => key === path[i]));
    if (locked) {
      body.append(el("p", `${display(value)} · Edit this value in Raw YAML.`, { className: "notice" }));
      main.append(field); return;
    }
    if (value !== null && typeof value === "object") {
      const summary = Array.isArray(value) ? `${value.length} items` : Object.keys(value).join(", ") || "Empty object";
      const open = button("Edit fields →", () => navigate(path), "link");
      open.id = id;
      body.append(el("span", summary, { className: "field-summary", title: summary }), open);
    } else {
      const graphContext = PtkDependencies.context(schema, state.value, path, S);
      const graphChange = graphContext && ["job", "title", "needs", "run", "python", "uses", "generators"].includes(path[graphContext.path.length + 1]);
      const input = control(value, spec, next => change({ op: "set", path, value: next, ...(graphChange ? { render: true } : {}) }), id, path);
      const hint = el("p", required ? "Required — enter a value." : "Empty — enter a value.", { className: "empty-field-message", id: `${id}-empty` });
      const markEmpty = () => {
        const empty = typeof value === "string" ? !input.value.trim() : value === null && required;
        field.classList.toggle("needs-value", empty);
        hint.hidden = !empty;
        if (empty && required || input.hasAttribute("data-number-invalid")) input.setAttribute("aria-invalid", "true");
        else input.removeAttribute("aria-invalid");
      };
      input.setAttribute("aria-describedby", [help && helpId, hint.id].filter(Boolean).join(" "));
      if (required) input.setAttribute("aria-required", "true");
      input.addEventListener("input", markEmpty); input.addEventListener("change", markEmpty);
      markEmpty(); body.append(input, hint);
      if (typeof value === "string" && (input.tagName === "TEXTAREA" || input.type === "text")) variableControl(body, input, path);
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
  function variableControl(field, input, path) {
    const entries = PtkVariables.available(state, schema, path, S);
    if (!entries.length) return;
    const tools = el("div", undefined, { className: "variable-tools" });
    const popup = el("div", undefined, { className: "variable-picker", hidden: "", role: "region", "aria-label": "Insert variable" });
    const search = el("input", undefined, { type: "search", placeholder: "Search variables…", "aria-label": "Search variables", autocomplete: "off" });
    const results = el("div", undefined, { className: "variable-results", role: "listbox", id: `${input.id}-variables`, "aria-label": "Variables" });
    const summary = el("p", undefined, { className: "help", role: "status" });
    const close = (focus = false) => {
      if (variablePicker?.input !== input) return;
      popup.hidden = true; variablePicker = undefined;
      input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant");
      search.removeAttribute("aria-activedescendant");
      if (focus) input.focus({ preventScroll: true });
      if (renderPending && !pointerActive) renderConfiguration();
    };
    let range, matches = [], active = 0, automatic = false, inserting = false;
    function highlight() {
      [...results.children].forEach((node, i) => node.setAttribute("aria-selected", String(i === active)));
      const current = results.children[active], target = automatic ? input : search;
      if (current) { target.setAttribute("aria-activedescendant", current.id); current.scrollIntoView({ block: "nearest" }); }
      else target.removeAttribute("aria-activedescendant");
    }
    function insert(entry) {
      const text = "${" + entry.reference + "}";
      input.setRangeText(text, range.start, range.end, "end");
      // Queue locally, exactly like typing. Insertion never reloads PTK.
      inserting = true; input.dispatchEvent(new Event("input", { bubbles: true })); inserting = false;
      if (entry.placeholder) {
        const start = range.start + 2 + entry.reference.indexOf(entry.placeholder);
        input.setSelectionRange(start, start + entry.placeholder.length);
      }
      close(true);
    }
    function show(query) {
      matches = PtkVariables.filter(entries, query); active = 0;
      results.replaceChildren();
      for (const [index, entry] of matches.entries()) {
        const option = button("", () => insert(entry), "variable-option");
        option.id = `${results.id}-${index}`; option.setAttribute("role", "option"); option.tabIndex = -1;
        option.append(el("span", "${" + entry.reference + "}", { className: "variable-name" }),
          el("span", entry.group, { className: "badge" }),
          el("span", [entry.description, entry.availability].filter(Boolean).join(" "), { className: "help" }));
        option.addEventListener("pointerdown", event => event.preventDefault());
        results.append(option);
      }
      summary.textContent = matches.length ? `${matches.length} variables · ↑/↓ select · Enter inserts · Esc closes` : "No matching variables.";
      highlight();
    }
    function open(auto = false) {
      if (variablePicker?.input !== input) variablePicker?.close();
      automatic = auto;
      range = PtkVariables.token(input.value, input.selectionStart) || { start: input.selectionStart, end: input.selectionEnd, query: "" };
      popup.hidden = false; search.hidden = auto;
      variablePicker = { input, close, field };
      input.setAttribute("aria-expanded", "true");
      search.value = auto ? range.query : "";
      show(search.value);
      if (!auto) search.focus();
    }
    const launch = button("${}", () => open(), "secondary small");
    launch.setAttribute("aria-label", "Insert variable…");
    launch.title = "Insert variable (or type ${)";
    launch.addEventListener("pointerdown", event => event.preventDefault());
    launch.addEventListener("blur", event => { if (popup.hidden && !field.contains(event.relatedTarget)) flush(); });
    function keys(event) {
      if (popup.hidden) return;
      if (["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault(); active = matches.length ? (active + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length : 0; highlight();
      } else if (event.key === "Enter" && matches[active]) { event.preventDefault(); insert(matches[active]); }
      else if (event.key === "Escape") { event.preventDefault(); close(true); }
      else if (event.key === "Tab") { close(); flush(); }
    }
    input.addEventListener("keydown", keys); search.addEventListener("keydown", keys);
    input.addEventListener("input", () => {
      if (inserting) return;
      if (PtkVariables.token(input.value, input.selectionStart)) open(true);
      else close();
    });
    search.addEventListener("input", () => show(search.value));
    const moved = () => {
      if (variablePicker?.input === input && automatic) {
        if (PtkVariables.token(input.value, input.selectionStart)) open(true);
        else close();
      }
    };
    input.addEventListener("click", moved);
    input.addEventListener("keyup", event => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) moved(); });
    field.addEventListener("focusout", event => {
      if (variablePicker?.input === input && event.relatedTarget && !field.contains(event.relatedTarget)) { close(); flush(); }
    });
    search.setAttribute("aria-controls", results.id); input.setAttribute("aria-controls", results.id);
    input.setAttribute("aria-autocomplete", "list");
    popup.append(search, results, summary, button("Close", () => close(true), "secondary small"));
    tools.append(launch);
    field.append(tools, popup);
  }
  function addField(main, value, spec, resolved) {
    const missing = S.orderedEntries(spec, {}, schema, { includeMissing: true }).filter(([key]) => !Object.hasOwn(value, key));
    if (!Array.isArray(value) && resolved.additionalProperties === false && !missing.length) return;
    const isJob = selected.length === 1 && selected[0] === "jobs";
    const label = isJob ? "New job" : resolved["x-ptk-graph"] === "step" ? "New step" : resolved["x-ptk-graph"] === "job" ? "New workflow job" : Array.isArray(value) ? "New item" : "New field";
    const box = el("fieldset", undefined, { className: "add" });
    box.append(el("legend", label), el("p", "Choose → Configure → Review. Setup explains each field and prepares a draft before adding it.", { className: "help" }), button(`Set up ${label.toLowerCase()}`, () => startCreation([...selected]), ""));
    main.append(box);
  }
  function startCreation(path, defaults = {}) {
    afterEdits(() => {
      if (creation) { showIssue("Finish or cancel the current setup first."); return; }
      const parent = valueAt(path);
      if (!parent || typeof parent !== "object") throw new Error("The parent field no longer exists.");
      if (state.locked.some(prefix => prefix.length <= path.length && prefix.every((key, i) => key === path[i]))) throw new Error("Use Raw YAML to edit this locked field.");
      const spec = S.at(schema, state.value, path, schema);
      const holder = el("div");
      const draft = { path, submitting: false, needsFocus: true };
      draft.api = PtkCreation.mount(holder, {
        S, schema, parent: structuredClone(parent), spec, path, defaults,
        jobChoices: S.resolve(spec, schema)["x-ptk-graph"] === "job" ? PtkDependencies.availableJobs(state.logical ? state.value : state.configurationValue, parent) : undefined,
        configuration: state.logical ? state.value : state.configurationValue,
        label: Array.isArray(parent) ? "new item" : "new element",
        input: control, variables: variableControl,
        onCancel: () => { if (!draft.submitting) { variablePicker?.close(); creation = undefined; renderConfiguration(); } },
        onCreate: (key, value) => {
          const current = valueAt(path);
          if (!current || typeof current !== "object") throw new Error("The parent field no longer exists. Cancel and reopen setup.");
          const currentSpec = S.at(schema, state.value, path, schema);
          const resolved = S.effective(currentSpec, current, schema);
          const index = PtkCreation.fieldName(current, String(key), resolved);
          const child = S.child(currentSpec, current, index, schema);
          const errors = PtkCreation.problems(S, child, schema, value);
          if (errors.length) throw new Error(errors.slice(0, 8).join("\n"));
          if (resolved["x-ptk-graph"]) PtkDependencies.validate(PtkDependencies.nodes({ ...current, [index]: value }));
          if (resolved["x-ptk-graph"] === "job") PtkDependencies.validateTargets({ ...current, [index]: value }, (state.logical ? state.value : state.configurationValue)?.repository?.alias);
          variablePicker?.close();
          draft.submitting = true; draft.api.setBusy(true);
          deferred.push(() => {
            creation = undefined;
            selected = value !== null && typeof value === "object" ? [...path, index] : path;
            remember(); renderConfiguration();
          });
          change({ op: "add", path: [...path, index], value }, true);
          draft.editId = inflight?.id;
        },
      });
      creation = draft;
      renderConfiguration();
    });
  }
  function variantControls(container, selected, onChange) {
    const choices = state.variantChoices || [];
    if (!choices.length) return () => [];
    const section = el("section", undefined, { className: "run-variants" });
    section.append(el("h2", state.kind === "workflow" ? "Owner variants" : "Variants"));
    section.append(el("p", "Select one or more variants to run in parallel. An empty selection automatically selects the project default." + (state.kind === "workflow" ? " PTK applies repository mappings separately to each owner variant." : ""), { className: "help" }));
    if (state.variantHelp) {
      const details = el("details"); details.append(el("summary", "Variant help"), el("p", state.variantHelp, { className: "help" })); section.append(details);
    }
    const all = el("input", undefined, { type: "checkbox", "aria-label": "All variants" });
    const allLabel = el("label", undefined, { className: "variant-choice" });
    allLabel.append(all, el("span", "All variants")); section.append(allLabel);
    const inputs = choices.map(item => {
      const label = el("label", undefined, { className: "variant-choice" });
      const input = el("input", undefined, { type: "checkbox", name: "run-variant", value: item.name, "aria-label": item.name });
      input.checked = selected.includes(item.name);
      const text = el("span", item.name + (item.name === state.defaultVariant ? " (default)" : ""));
      if (item.description) text.append(el("small", item.description, { className: "help" }));
      if (item.aliases?.length) text.append(el("small", `Aliases: ${item.aliases.join(", ")}`, { className: "help" }));
      label.append(input, text); section.append(label);
      return input;
    });
    const names = () => inputs.filter(input => input.checked).map(input => input.value);
    const sync = () => {
      if (!names().length) {
        const defaultInput = inputs.find(input => input.value === state.defaultVariant);
        if (defaultInput) defaultInput.checked = true;
      }
      all.checked = inputs.every(input => input.checked);
      all.indeterminate = !all.checked && inputs.some(input => input.checked);
      onChange(names()); showIssue("");
    };
    for (const input of inputs) input.addEventListener("change", sync);
    all.addEventListener("change", () => { for (const input of inputs) input.checked = all.checked; sync(); });
    // Establish the default before the first render without invoking the form callback.
    if (!names().length) { const input = inputs.find(input => input.value === state.defaultVariant); if (input) input.checked = true; }
    all.checked = inputs.every(input => input.checked);
    all.indeterminate = !all.checked && inputs.some(input => input.checked);
    container.append(section);
    return names;
  }

  function executionControls(container) {
    const specs = state.runOptions || [];
    if (!specs.length) return () => ({});
    const section = el("section", undefined, { className: "run-options" });
    section.append(el("h2", "Run options"));
    const advanced = el("details"); advanced.append(el("summary", "More run options"));
    const controls = [];
    for (const spec of specs) {
      const id = `run-option-${spec.name}`;
      const field = el("div", undefined, { className: "run-option" });
      const label = el("label", spec.option, { for: id });
      const description = el("p", spec.help || "Optional; omit to use PTK's default.", { className: "help", id: `${id}-help` });
      let input;
      if (spec.choices.length) {
        input = el("select", undefined, { id });
        input.append(el("option", "Use default", { value: "" }));
        for (const value of spec.choices) {
          const detail = spec.suggestions?.find(item => item.value === value)?.help;
          input.append(el("option", detail && detail !== "Top-level step" ? `${value} — ${detail}` : value, { value }));
        }
      } else if (spec.multiple) {
        input = el("textarea", undefined, { id, rows: 2, placeholder: "One value per line" });
        description.append(document.createTextNode(" Enter one value per line; spaces within each value are preserved."));
      } else input = el("input", undefined, { id, type: spec.is_flag ? "checkbox" : "text" });
      input.setAttribute("aria-describedby", `${id}-help`);
      field.append(label, input, description);
      if (!spec.choices.length && spec.suggestions?.length) {
        const suggestions = el("div", undefined, { className: "run-suggestions", "aria-label": `${spec.option} suggestions` });
        for (const item of spec.suggestions) {
          const action = button(item.value, () => {
            input.value = spec.multiple && input.value ? `${input.value}\n${item.value}` : item.value;
            input.focus(); showIssue("");
          });
          action.title = item.help || item.value;
          suggestions.append(action);
        }
        field.append(suggestions);
      }
      input.addEventListener("input", () => showIssue(""));
      (spec.name === "only_step" || spec.name === "end" ? section : advanced).append(field);
      controls.push({ spec, input });
    }
    section.append(advanced); container.append(section);
    return () => Object.fromEntries(controls.flatMap(({ spec, input }) => {
      const values = spec.is_flag ? input.checked ? ["true"] : [] : spec.multiple ? input.value.split(/\r?\n/).filter(value => value.trim()) : input.value ? [input.value] : [];
      return values.length ? [[spec.name, values]] : [];
    }));
  }

  function renderParameters() {
    app.replaceChildren();
    app.className = "parameter-editor";
    const header = el("header");
    const variants = state.variants || [];
    header.append(el("div", `PTk / ${state.kind === "workflow" ? "Workflow" : "Job"} options`, { className: "brand" }), el("h1", state.name), el("p", [state.project, variants.length && `${variants.length > 1 ? "Variants (parallel)" : "Variant"}: ${variants.join(", ")}`].filter(Boolean).join(" · "), { className: "muted" }));
    app.append(header);
    const main = el("main", undefined, { className: "parameters" });
    notice(main);
    if (state.help) main.append(el("p", state.help));
    const selectedVariants = variantControls(main, variants, names => {
      const selected = names.length ? names : state.defaultVariant ? [state.defaultVariant] : [];
      header.querySelector("p").textContent = [state.project, selected.length && `${selected.length > 1 ? "Variants (parallel)" : "Variant"}: ${selected.join(", ")}`].filter(Boolean).join(" · ");
    });
    const runOptions = executionControls(main);
    if (state.params.length) main.append(el("p", "Enable an override to supply a value. Otherwise PTK uses the configured environment or default when the job runs.", { className: "muted" }));
    if (variants.length > 1 || state.kind === "job" && state.variantChoices?.length > 1) main.append(el("p", "Overrides apply to every selected variant. Omitted values and template defaults are resolved separately for each run.", { className: "help" }));
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
    if (!state.params.length && state.kind !== "workflow") main.append(el("p", "This job has no non-secret parameters.", { className: "empty" }));
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
      vscode.postMessage({ type: "submit", preview, params, runOptions: runOptions(), variants: selectedVariants() });
    }
    footer.append(button("Cancel", () => vscode.postMessage({ type: "cancel" })),
      button("Dry run", () => submit(true), state.preview ? "" : "secondary"),
      button(state.reRun ? "Clean & re-run" : state.kind === "workflow" ? "Run workflow" : "Run job", () => submit(false), state.preview ? "secondary" : ""));
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
    const creationAck = creation?.submitting && message.ack === creation.editId;
    if (!own && inflight && message.version === state.version) return;
    if (!own && (queue.size || inflight) || message.issue) {
      if (own && message.issue) {
        const drafts = [...queue.values()];
        queue.clear();
        // A rejected connection is an action, not a text draft. Do not replay
        // it ahead of the user's repair or next selection after a stale save.
        for (const operation of [...submitted.filter(op => op.op !== "dependency" && !creationAck), ...drafts]) queue.set(JSON.stringify(operation.path), operation);
      }
      commitRequested = false; deferred.length = 0;
      issue = message.issue || "The document changed outside this form. Review the refreshed fields before editing again.";
    } else if (message.issue === undefined) issue = "";
    if (creation?.submitting && (message.issue || !own && message.version !== state.version)) {
      creation.submitting = false;
      creation.api.issue(message.issue || "The configuration changed. Review your draft before creating it again.");
    }
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
  document.addEventListener("pointerdown", event => {
    if (app.contains(event.target)) pointerActive = true;
    if (variablePicker && !variablePicker.field.contains(event.target)) { variablePicker.close(); flush(); }
  });
  const finishPointer = () => setTimeout(() => {
    pointerActive = false;
    if (renderPending) renderConfiguration();
  }, 0);
  document.addEventListener("pointerup", finishPointer);
  document.addEventListener("pointercancel", finishPointer);
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && state?.mode === "configuration") {
      event.preventDefault();
      if (creation) { showIssue("This setup draft is not saved yet. Finish with Review and Create, or cancel setup."); return; }
      afterEdits(() => vscode.postMessage({ type: "save" }));
    }
  });
  vscode.postMessage({ type: "ready" });
})();
