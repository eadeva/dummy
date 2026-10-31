/* Schema-driven, memory-only setup drafts. Only the final callback writes. */
(function (root, factory) {
  if (typeof module === "object") module.exports = factory();
  else root.PtkCreation = factory();
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const forbidden = new Set(["__proto__", "constructor", "prototype"]);
  const types = (S, spec, schema) => {
    const result = [...new Set(S.choices(spec, schema).map(part => part.type).filter(Boolean))];
    return result.length ? result : ["string", "number", "boolean", "object", "array", "null"];
  };
  function problems(S, spec, schema, value, path = "Value", depth = 0) {
    if (depth > 30) return [`${path}: nesting is too deep for this form.`];
    const kinds = types(S, spec, schema), kind = S.type(value);
    if (kinds.length && !kinds.includes(kind) && !(kind === "integer" && kinds.includes("number"))) return [`${path}: expected ${kinds.join(" or ")}.`];
    const rule = S.effective(spec, value, schema), result = [];
    if (rule.enum && !rule.enum.some(item => JSON.stringify(item) === JSON.stringify(value))) result.push(`${path}: choose an allowed value.`);
    if (Object.hasOwn(rule, "const") && rule.const !== value) result.push(`${path}: must be ${rule.const}.`);
    if (typeof value === "string") {
      if (rule.minLength !== undefined && [...value].length < rule.minLength) result.push(`${path}: enter at least ${rule.minLength} characters.`);
      if (rule.maxLength !== undefined && [...value].length > rule.maxLength) result.push(`${path}: use at most ${rule.maxLength} characters.`);
      if (rule.pattern && !new RegExp(rule.pattern).test(value)) result.push(`${path}: must match ${rule.pattern}.`);
    }
    if (typeof value === "number") {
      if (!Number.isFinite(value) || Number.isInteger(value) && !Number.isSafeInteger(value)) result.push(`${path}: enter a finite, precisely representable number.`);
      for (const [key, invalid, message] of [["minimum", value < rule.minimum, "at least"], ["maximum", value > rule.maximum, "at most"], ["exclusiveMinimum", value <= rule.exclusiveMinimum, "greater than"], ["exclusiveMaximum", value >= rule.exclusiveMaximum, "less than"]]) if (invalid) result.push(`${path}: must be ${message} ${rule[key]}.`);
    }
    if (value !== null && typeof value === "object") {
      const array = Array.isArray(value), entries = Object.entries(value);
      const minimum = array ? rule.minItems : rule.minProperties, maximum = array ? rule.maxItems : rule.maxProperties;
      if (minimum !== undefined && entries.length < minimum) result.push(`${path}: add at least ${minimum} ${array ? "items" : "fields"}.`);
      if (maximum !== undefined && entries.length > maximum) result.push(`${path}: use at most ${maximum} ${array ? "items" : "fields"}.`);
      for (const name of rule.required || []) if (!Object.hasOwn(value, name)) result.push(`${path}.${name}: required field is missing.`);
      for (const [name, child] of entries) {
        if (forbidden.has(name)) { result.push(`${path}: invalid field name.`); continue; }
        if (!array && rule.additionalProperties === false && !Object.hasOwn(rule.properties || {}, name)) result.push(`${path}.${name}: unknown field.`);
        if (!array && rule.propertyNames?.pattern && !new RegExp(rule.propertyNames.pattern).test(name)) result.push(`${path}.${name}: invalid name.`);
        result.push(...problems(S, S.child(spec, value, name, schema), schema, child, `${path}.${name}`, depth + 1));
      }
    }
    return result;
  }
  function fieldName(parent, name, spec) {
    if (Array.isArray(parent)) return parent.length;
    const key = name.trim();
    if (!key || forbidden.has(key)) throw new Error("Enter a valid name.");
    if (Object.hasOwn(parent, key)) throw new Error(`“${key}” already exists. Choose a different name.`);
    if (spec.additionalProperties === false && !Object.hasOwn(spec.properties || {}, key)) throw new Error("Choose an available field.");
    if (spec.propertyNames?.pattern && !new RegExp(spec.propertyNames.pattern).test(key)) throw new Error(spec.propertyNames.description || `The name must match ${spec.propertyNames.pattern}.`);
    if (spec.propertyNames?.not?.enum?.includes(key)) throw new Error(`“${key}” is reserved. Choose a different name.`);
    return key;
  }
  function mount(container, options) {
    const { S, schema, parent, spec, path, configuration, input, variables, onCreate, onCancel } = options;
    const parentSpec = S.effective(spec, parent, schema), isList = Array.isArray(parent);
    const namedFields = !isList && parentSpec.additionalProperties === false;
    const fields = S.orderedEntries(spec, {}, schema, { includeMissing: true }).map(([key]) => key).filter(key => !Object.hasOwn(parent, key));
    const state = { page: 0, name: namedFields ? fields[0] || "" : "", type: "", mode: "", draft: undefined, initialized: false, seed: "", busy: false, error: "" };
    let lastPage = -1;
    const node = document.createElement("section"); node.className = "creation-wizard"; node.setAttribute("aria-label", "Configuration setup");
    container.append(node);
    function el(tag, text, attrs = {}) {
      const n = document.createElement(tag);
      if (text !== undefined) n.textContent = text;
      for (const [key, value] of Object.entries(attrs)) n.setAttribute(key, value);
      return n;
    }
    function button(label, callback, secondary = true) {
      const n = el("button", label, { type: "button", class: secondary ? "secondary" : "" });
      n.disabled = state.busy; n.addEventListener("click", () => { try { callback(); } catch (error) { state.error = error.message; render(); } }); return n;
    }
    function childSpec() { return S.child(spec, parent, isList ? parent.length : state.name, schema); }
    function modeOptions(child) {
      const resolved = S.resolve(child, schema);
      return resolved["x-ptk-creation-modes"] || ["StepSpec", "JobSpec", "PythonSpec"].includes(resolved.title) ? S.stepModes(child, schema) : [];
    }
    function context() { return { name: state.name.trim(), existing: isList ? parent : [], configuration }; }
    function chosenSpec() { return S.choices(childSpec(), schema).find(choice => choice.type === state.type) || childSpec(); }
    function initialize() {
      const modes = modeOptions(childSpec());
      const seed = JSON.stringify([modes.length ? state.mode : state.type, namedFields ? state.name : ""]);
      if (state.initialized && state.seed === seed) return;
      state.draft = modes.length ? S.stepInitial(childSpec(), schema, state.mode) : S.initial(chosenSpec(), schema, context());
      if (state.draft && typeof state.draft === "object" && !Array.isArray(state.draft)) Object.assign(state.draft, structuredClone(options.defaults || {}));
      if (options.jobChoices && !options.jobChoices.includes(state.draft.job)) state.draft.job = options.jobChoices[0] || "";
      const directory = S.resolve(childSpec(), schema)["x-ptk-directory-template"];
      if (directory) state.draft.path = directory.replace("{name}", state.name.trim());
      state.seed = seed; state.initialized = true;
    }
    function validate() {
      const bad = node.querySelector('[data-number-invalid="true"]');
      if (bad) { bad.focus(); throw new Error("Enter a valid number before continuing."); }
      const issues = problems(S, chosenSpec(), schema, state.draft);
      if (issues.length) throw new Error(issues.slice(0, 8).join("\n"));
    }
    function setAt(keys, value) {
      if (!keys.length) state.draft = value;
      else keys.slice(0, -1).reduce((o, key) => o[key], state.draft)[keys.at(-1)] = value;
      state.error = "";
    }
    function help(target, title, text) {
      if (!text) return;
      const details = el("details", undefined, { class: "creation-help" });
      details.append(el("summary", title), el("p", text, { class: "help" })); target.append(details);
    }
    function editValue(target, value, field, keys, label, required = false, depth = 0) {
      if (depth > 20) { target.append(el("p", "Use Raw YAML for deeper nesting after creation.", { class: "help" })); return; }
      const resolved = S.effective(field, value, schema), id = `create-value-${JSON.stringify(keys)}`;
      const row = el("div", undefined, { class: "creation-field" });
      const top = el("div", undefined, { class: "row" });
      top.append(el("label", `${label}${required ? " *" : ""}`, { for: id }));
      const variants = types(S, field, schema);
      if (variants.length > 1) {
        const select = el("select", undefined, { "aria-label": `${label} value type` });
        variants.forEach(kind => select.append(el("option", kind, { value: kind })));
        select.value = S.type(value) === "integer" && !variants.includes("integer") ? "number" : S.type(value);
        select.addEventListener("change", () => { setAt(keys, S.initial(S.choices(field, schema).find(choice => choice.type === select.value), schema, context())); render(); }); top.append(select);
      }
      row.append(top);
      if (resolved.description) row.append(el("p", resolved.description, { class: "help" }));
      help(row, "Type, defaults and limits", S.help(field, value, schema));
      if (value === null || typeof value !== "object") {
        const control = input(value, field, next => setAt(keys, next), id, [...path, isList ? parent.length : state.name, ...keys]);
        if (required) control.setAttribute("aria-required", "true");
        row.append(control);
        if (typeof value === "string" && (control.tagName === "TEXTAREA" || control.type === "text")) variables?.(row, control, [...path, isList ? parent.length : state.name, ...keys]);
      } else {
        const array = Array.isArray(value);
        if (keys.length && resolved["x-ptk-creation-modes"]) {
          const modes = modeOptions(field), select = el("select", undefined, { "aria-label": `Starting mode for ${label}` });
          select.append(el("option", "Choose another starting mode…", { value: "" }));
          modes.forEach(mode => select.append(el("option", mode.label, { value: mode.id })));
          const details = el("p", "Changing mode replaces this object's draft fields.", { class: "help", "aria-live": "polite" });
          const apply = button(`Use mode for ${label}`, () => { setAt(keys, S.stepInitial(field, schema, select.value)); render(); }); apply.disabled = true;
          select.addEventListener("change", () => { const mode = modes.find(mode => mode.id === select.value); apply.disabled = !mode; details.textContent = mode ? `${mode.description} Requires: ${mode.requirements} Keep in mind: ${mode.constraints} Changing mode replaces this object's draft fields.` : "Choose a mode."; });
          row.append(select, details, apply);
        }
        const entries = S.orderedEntries(field, value, schema);
        for (const [key, child] of entries) {
          const entry = el("div", undefined, { class: "creation-entry" });
          editValue(entry, child, S.child(field, value, key, schema), [...keys, array ? Number(key) : key], array ? `Item ${Number(key) + 1}` : key, (resolved.required || []).includes(key), depth + 1);
          if (!(resolved.required || []).includes(key)) entry.append(button(`Remove ${array ? "item " + (Number(key) + 1) : key}`, () => { array ? value.splice(Number(key), 1) : delete value[key]; render(); }));
          row.append(entry);
        }
        const missing = S.orderedEntries(field, {}, schema, { includeMissing: true }).map(([key]) => key).filter(key => !Object.hasOwn(value, key));
        if (array || resolved.additionalProperties !== false || missing.length) {
          const addRow = el("div", undefined, { class: "creation-add row" });
          let name;
          if (!array) {
            name = el(resolved.additionalProperties === false ? "select" : "input", undefined, { "aria-label": `New field in ${label}` });
            missing.forEach(key => { if (name.tagName === "SELECT") name.append(el("option", key, { value: key })); });
            if (name.tagName === "INPUT") name.placeholder = "Name";
            addRow.append(name);
          }
          const fieldHelp = el("p", "", { class: "help", "aria-live": "polite" });
          const mode = el("select", undefined, { "aria-label": `Mode for new entry in ${label}` });
          const modeHelp = el("p", "", { class: "help", "aria-live": "polite" });
          let entryModes = [];
          const describeMode = () => { const chosen = entryModes.find(item => item.id === mode.value); modeHelp.textContent = chosen ? `${chosen.description} Requires: ${chosen.requirements} Keep in mind: ${chosen.constraints}` : "Choose an execution mode before adding this entry to the draft."; };
          const describeField = () => {
            const child = S.child(field, value, array ? value.length : name.value, schema);
            fieldHelp.textContent = S.help(child, undefined, schema);
            entryModes = modeOptions(child);
            const previous = mode.value;
            mode.replaceChildren(el("option", "Choose a mode…", { value: "" }));
            entryModes.forEach(item => mode.append(el("option", item.label, { value: item.id })));
            mode.value = entryModes.some(item => item.id === previous) ? previous : "";
            mode.hidden = modeHelp.hidden = !entryModes.length; describeMode();
          };
          mode.addEventListener("change", describeMode);
          name?.addEventListener(name.tagName === "SELECT" ? "change" : "input", describeField); describeField();
          addRow.append(button(array ? `Add item to ${label}` : `Add field to ${label}`, () => {
            const key = fieldName(value, name?.value || "", resolved);
            const child = S.child(field, value, key, schema);
            const next = modeOptions(child).length ? S.stepInitial(child, schema, mode.value) : S.initial(child, schema, { ...context(), name: key, existing: array ? value : [] });
            if (array) value.push(next); else value[key] = next;
            render();
          })); row.append(addRow, fieldHelp, mode, modeHelp);
        }
      }
      target.append(row);
    }
    function render() {
      const focused = document.activeElement?.getAttribute("id");
      const changedPage = lastPage !== state.page; lastPage = state.page;
      node.replaceChildren();
      const titles = ["Choose", "Configure", "Review"];
      const progress = el("ol", undefined, { class: "creation-progress", "aria-label": "Setup progress" });
      titles.forEach((title, index) => progress.append(el("li", `${index + 1}. ${title}`, index === state.page ? { "aria-current": "step" } : {})));
      const heading = el("h2", `${titles[state.page]} ${options.label || "new configuration"}`, { tabindex: "-1" });
      node.append(progress, heading);
      node.append(el("p", `Location: ${[...path, state.name || (isList ? `item ${parent.length + 1}` : "new field")].join(" / ")}`, { class: "help" }));
      const issue = el("p", state.error, { class: "notice error", role: "alert" }); issue.hidden = !state.error; node.append(issue);
      if (state.page === 0) {
        node.append(el("p", parentSpec.description || "Choose a name or field and its starting configuration.", { class: "help" }));
        if (!isList) {
          const name = el(namedFields ? "select" : "input", undefined, { id: "creation-name", "aria-label": namedFields ? "Field to add" : "New element name" });
          if (namedFields) fields.forEach(key => name.append(el("option", key, { value: key })));
          name.value = state.name; if (!namedFields) name.placeholder = "Choose a descriptive name";
          name.addEventListener(namedFields ? "change" : "input", () => { state.name = name.value; state.error = ""; if (namedFields) { state.type = ""; state.mode = ""; render(); } });
          node.append(el("label", namedFields ? "Field to add" : "Name", { for: "creation-name" }), name);
          if (parentSpec.propertyNames?.description) node.append(el("p", parentSpec.propertyNames.description, { class: "help" }));
        }
        const child = childSpec();
        if (S.resolve(child, schema).description) node.append(el("p", S.resolve(child, schema).description, { class: "help" }));
        help(node, "Field details, defaults and limits", S.help(child, undefined, schema));
        let modes = [];
        try { modes = modeOptions(child); } catch (error) { node.append(el("p", error.message, { class: "notice error", role: "alert" })); }
        if (modes.length) {
          const select = el("select", undefined, { id: "creation-mode", "aria-describedby": "creation-mode-help" });
          select.append(el("option", "Choose a mode…", { value: "" }));
          const groups = new Map();
          for (const mode of modes) {
            if (!groups.has(mode.group)) { const group = el("optgroup", undefined, { label: mode.group }); groups.set(mode.group, group); select.append(group); }
            groups.get(mode.group).append(el("option", mode.label, { value: mode.id }));
          }
          select.value = state.mode;
          select.addEventListener("change", () => { state.mode = select.value; state.error = ""; render(); });
          node.append(el("label", S.resolve(child, schema).title === "JobSpec" ? "First step mode" : "Execution mode", { for: "creation-mode" }), select);
          const details = el("div", undefined, { id: "creation-mode-help", "aria-live": "polite" });
          const mode = modes.find(m => m.id === state.mode);
          if (mode) {
            details.append(el("p", mode.description));
            for (const [field, label] of [["requirements", "Requires"], ["constraints", "Keep in mind"]]) { const p = el("p"); p.append(el("strong", `${label}: `), document.createTextNode(mode[field])); details.append(p); }
          }
          node.append(details);
        } else {
          const kinds = types(S, child, schema);
          if (kinds.length > 1) {
            const select = el("select", undefined, { id: "creation-type" });
            kinds.forEach(kind => select.append(el("option", kind, { value: kind })));
            if (!kinds.includes(state.type)) state.type = kinds.find(kind => kind !== "null") || kinds[0];
            select.value = state.type; select.addEventListener("change", () => { state.type = select.value; render(); });
            node.append(el("label", "Value type", { for: "creation-type" }), select);
          }
        }
        node.append(el("p", state.initialized ? "Going back keeps your draft. Changing its field, mode or value type starts a new draft when you continue." : "This setup only prepares configuration. Nothing is written until Create. Setup never executes commands or installs dependencies.", { class: "help" }));
      } else if (state.page === 1) {
        node.append(el("p", "Required fields are marked *. Review example commands and paths, then add optional fields as needed. Values remain in this draft until Create.", { class: "help" }));
        editValue(node, state.draft, chosenSpec(), [], state.name || "New item");
      } else {
        node.append(el("p", "Review the configuration below. Create adds this element; it does not run commands or install dependencies. Use Save & validate afterwards for full project checks.", { class: "help" }));
        node.append(el("pre", JSON.stringify(state.draft, null, 2), { class: "creation-preview", "aria-label": "Configuration preview" }));
      }
      const actions = el("div", undefined, { class: "actions creation-actions" });
      actions.append(button("Cancel setup", onCancel));
      if (state.page) actions.append(button("Back", () => { state.page--; state.error = ""; render(); }));
      actions.append(button(state.page === 2 ? "Create" : state.page === 1 ? "Review" : "Configure", () => {
        if (state.page === 0) { fieldName(parent, state.name, parentSpec); initialize(); state.page = 1; render(); }
        else if (state.page === 1) { validate(); state.page = 2; render(); }
        else { validate(); onCreate(fieldName(parent, state.name, parentSpec), structuredClone(state.draft)); }
      }, false));
      node.append(actions);
      if (state.busy) node.querySelectorAll("input, select, textarea, button").forEach(control => { control.disabled = true; });
      if (node.isConnected) {
        if (changedPage) heading.focus();
        else if (focused) [...node.querySelectorAll("input, select, textarea, button")].find(control => control.getAttribute("id") === focused)?.focus();
      }
    }
    render();
    return { node, setBusy(value) { state.busy = value; render(); }, issue(message) { state.error = message; state.busy = false; render(); } };
  }
  return { mount, problems, fieldName };
});
