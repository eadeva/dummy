/* global acquireVsCodeApi, PtkSchema, PtkPresentation, PtkVariables */
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
    if (node) node.textContent = inflight || deferred.length ? "Saving…" : queue.size ? "Editing · Leave the field or press Ctrl/Cmd+S to save" : state.dirty ? "Unsaved changes · Ctrl/Cmd+S to save" : "Saved";
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
      app.replaceChildren();
      app.className = "configuration";
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
    const field = el("section", undefined, { className: "field", "data-type": S.type(value) });
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
      const open = button("Edit fields →", () => navigate(P.namedEntry(value, path) ? [...path, P.namedEntry(value, path)] : path), "link");
      open.id = id;
      body.append(el("span", summary, { className: "field-summary", title: summary }), open);
    } else {
      const input = control(value, spec, next => change({ op: "set", path, value: next }), id);
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
    const containerPath = [...selected];
    const box = el("fieldset", undefined, { className: "add" });
    const isList = Array.isArray(value);
    const isJobs = selected.length === 1 && selected[0] === "jobs";
    box.append(el("legend", isJobs ? "Add a job" : isList ? "Add an item" : "Add a field"));
    const row = el("div", undefined, { className: "row" });
    let name, options = S.orderedEntries(spec, {}, schema, { includeMissing: true }).map(([key]) => key).filter(key => !Object.hasOwn(value, key));
    if (!isList && resolved.additionalProperties === false) {
      if (!options.length) return;
      name = el("select", undefined, { "aria-label": "Optional field" });
      for (const key of options) name.append(el("option", key, { value: key }));
    } else if (!isList) name = el("input", undefined, { placeholder: isJobs ? "e.g. build" : "Field name", "aria-label": isJobs ? "New job name" : "New field name" });
    const help = el("p", "", { className: "help" });
    if (name) {
      name.id = `add-name-${JSON.stringify(containerPath)}`;
      name.setAttribute("data-ui-draft", "true");
      const draft = uiDrafts.get(name.id);
      if (draft !== undefined && (name.tagName !== "SELECT" || options.includes(draft))) name.value = draft;
      const rememberName = () => uiDrafts.set(name.id, name.value);
      name.addEventListener("input", rememberName); name.addEventListener("change", rememberName);
      row.append(name);
      const describe = () => {
        const field = resolved.properties?.[name.value] || {};
        help.textContent = S.help(field, undefined, schema);
      };
      name.addEventListener("change", describe); describe();
    }
    row.append(button(isJobs ? "Add job" : isList ? "Add item" : "Add field", () => {
      const key = isList ? undefined : name.value.trim();
      if (!isList && (!key || ["__proto__", "constructor", "prototype"].includes(key))) { showIssue("Enter a valid field name."); return; }
      if (isJobs && !/^[a-z][a-z0-9-]*$/.test(key)) { showIssue("Job names must start with a lowercase letter and contain only lowercase letters, digits or hyphens."); return; }
      afterEdits(() => {
        const current = valueAt(containerPath);
        if (current === null || typeof current !== "object") throw new Error("The parent field no longer exists.");
        const index = isList ? current.length : key;
        if (!isList && Object.hasOwn(current, key)) throw new Error(`Field ${key} already exists.`);
        const currentSpec = S.at(schema, state.value, containerPath, schema);
        const child = S.child(currentSpec, current, index, schema);
        const next = S.initial(child, schema, { name: key, existing: isList ? current : [], configuration: state.configurationValue || state.value });
        const directory = S.resolve(child, schema)["x-ptk-directory-template"];
        if (directory) next.path = directory.replace("{name}", key);
        if (name?.tagName === "INPUT" && uiDrafts.get(name.id)?.trim() === key) {
          uiDrafts.delete(name.id);
          const visible = document.getElementById(name.id);
          if (visible) visible.value = "";
        }
        change({ op: "add", path: [...containerPath, index], value: next }, true);
      });
    }, ""));
    box.append(row, help); main.append(box);
  }
  function variantControls(container, selected, onChange) {
    const choices = state.variantChoices || [];
    if (!choices.length) return () => [];
    const section = el("section", undefined, { className: "run-variants" });
    section.append(el("h2", state.kind === "workflow" ? "Owner variant" : "Variants"));
    section.append(el("p", state.kind === "workflow" ? "Choose one owner variant. PTK applies its repository mappings." : "Select one or more variants to run in parallel. Choices apply to this run.", { className: "help" }));
    if (state.variantHelp) {
      const details = el("details"); details.append(el("summary", "Variant help"), el("p", state.variantHelp, { className: "help" })); section.append(details);
    }
    const defaults = state.defaultVariant ? `Use project default (${state.defaultVariant})` : "Use project default (none configured)";
    const inputs = [];
    for (const item of [{ name: "", description: defaults }, ...choices]) {
      const label = el("label", undefined, { className: "variant-choice" });
      const input = el("input", undefined, { type: state.kind === "workflow" ? "radio" : "checkbox", name: "run-variant", value: item.name, "aria-label": item.name || defaults });
      input.checked = item.name ? state.useDefault !== true && selected.includes(item.name) : state.useDefault === true || !selected.length;
      const text = el("span", item.name || defaults);
      if (item.name && item.description) text.append(el("small", item.description, { className: "help" }));
      if (item.aliases?.length) text.append(el("small", `Aliases: ${item.aliases.join(", ")}`, { className: "help" }));
      label.append(input, text); section.append(label); inputs.push(input);
      input.addEventListener("change", () => {
        if (input.checked && !item.name) for (const other of inputs) { if (other !== input) other.checked = false; }
        else if (input.checked) inputs[0].checked = false;
        if (!inputs.some(other => other.checked)) inputs[0].checked = true;
        onChange(inputs.filter(other => other.checked && other.value).map(other => other.value));
        showIssue("");
      });
    }
    container.append(section);
    return () => inputs.filter(input => input.checked && input.value).map(input => input.value);
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
      (spec.name === "start" || spec.name === "end" ? section : advanced).append(field);
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
    const variants = state.variants || (state.variant ? [state.variant] : []);
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
    if (!own && inflight && message.version === state.version) return;
    if (!own && (queue.size || inflight) || message.issue) {
      if (own && message.issue) {
        const drafts = [...queue.values()];
        queue.clear();
        for (const operation of [...submitted, ...drafts]) queue.set(JSON.stringify(operation.path), operation);
      }
      commitRequested = false; deferred.length = 0;
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
      event.preventDefault(); afterEdits(() => vscode.postMessage({ type: "save" }));
    }
  });
  vscode.postMessage({ type: "ready" });
})();
