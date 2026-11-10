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
    if (rule.title === "ParamSpec" && value && typeof value === "object") {
      const kind = value.type || "str", hasDefault = value.default !== undefined && value.default !== null;
      const template = typeof value.default === "string" && value.default.replaceAll("$${", "").includes("${");
      if (kind === "choice" && (!Array.isArray(value.choices) || !value.choices.length || value.choices.some(item => typeof item !== "string" || !item.trim()))) result.push(`${path}: add at least one non-empty choice.`);
      if (kind !== "choice" && value.choices != null) result.push(`${path}: choices are only valid for a choice parameter.`);
      if (hasDefault && (kind === "secret" || value.required)) result.push(`${path}: secret or required parameters cannot have a default.`);
      if (hasDefault && !template) {
        if (kind === "choice" && !value.choices?.includes(value.default)) result.push(`${path}: select a default from the allowed choices.`);
        if (["int", "float"].includes(kind) && (!String(value.default).trim() || !Number.isFinite(Number(value.default)) || kind === "int" && !Number.isInteger(Number(value.default)))) result.push(`${path}: enter a valid ${kind === "int" ? "whole" : "decimal"} number as default.`);
        if (kind === "bool" && ![true, false, "true", "false", "1", "0", "yes", "no", "on", "off", "y", "n"].includes(typeof value.default === "string" ? value.default.toLowerCase() : value.default)) result.push(`${path}: choose true or false as default.`);
      }
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
    if (options.editKey !== undefined) Object.assign(state, { page: 1, name: options.editKey, draft: structuredClone(parent[options.editKey]), initialized: true });
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
      const declared = S.effective(childSpec(), state.draft, schema);
      if (namedFields && typeof state.draft === "boolean" && typeof declared.default === "boolean" && !(parentSpec.required || []).includes(state.name)) state.draft = !declared.default;
      if (state.draft && typeof state.draft === "object" && !Array.isArray(state.draft)) Object.assign(state.draft, structuredClone(options.defaults || {}));
      const directory = S.resolve(childSpec(), schema)["x-ptk-directory-template"];
      if (directory) state.draft.path = directory.replace("{name}", state.name.trim());
      defaultModes.clear();
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
    function parameterForm(target, value, field, keys) {
      const kind = value.type || "str";
      const prefix = `parameter-definition-${JSON.stringify(keys)}`;
      const labels = { str: "Text — names, labels and arguments", int: "Whole number — counts and limits", float: "Decimal number — ratios and thresholds", bool: "On / off — Boolean flag", choice: "Choice — select from allowed values", path: "Path — file or directory", list: "List — multiple text values", secret: "Secret — environment or hidden prompt" };
      const add = (label, control, description) => {
        const row = el("div", undefined, { class: "creation-field" });
        row.append(el("label", label, { for: control.getAttribute("id") }), control);
        if (description) row.append(el("p", description, { class: "help" }));
        target.append(row); return row;
      };
      const text = (key, label, description, multiline = false) => {
        const control = el(multiline ? "textarea" : "input", undefined, { id: `${prefix}-${key}` });
        control.value = value[key] || "";
        control.addEventListener("input", () => { if (control.value || key === "help") value[key] = control.value; else delete value[key]; });
        add(label, control, description); return control;
      };
      const type = el("select", undefined, { id: `${prefix}-type` });
      S.resolve(field, schema).properties.type.enum.forEach(item => type.append(el("option", labels[item] || item, { value: item })));
      type.value = kind;
      type.addEventListener("change", () => {
        value.type = type.value; delete value.default; delete value.choices; defaultModes.delete(JSON.stringify(keys));
        if (type.value === "choice") value.choices = [];
        render();
      });
      add("Parameter type", type, "Changing the type clears its default and choice list. Other settings are kept; Cancel leaves the saved parameter unchanged.");
      text("help", "Description shown to developers", "Explain what this parameter changes. Shown in command help and the run form.", true);
      if (kind === "choice") {
        const choices = el("textarea", undefined, { id: `${prefix}-choices` });
        choices.value = (value.choices || []).join("\n");
        choices.addEventListener("input", () => {
          value.choices = choices.value.split("\n").filter(item => item.trim());
          const current = [...node.querySelectorAll("select")].find(control => control.getAttribute("id") === `${prefix}-default`);
          if (current) {
            current.replaceChildren();
            if (!value.choices.includes(value.default)) current.append(el("option", "Choose a default…", { value: "" }));
            value.choices.forEach(choice => current.append(el("option", choice, { value: choice })));
            current.value = value.choices.includes(value.default) ? value.default : "";
          }
        });
        add("Allowed choices (one per line)", choices, "Use exact values, such as Debug and Release. At least one is required.");
      }
      const required = el("input", undefined, { id: `${prefix}-required`, type: "checkbox" });
      required.checked = Boolean(value.required);
      required.addEventListener("change", () => { value.required = required.checked; if (value.required) delete value.default; render(); });
      add("Require a value", required, "The developer must supply a value through an argument or environment variable. Enabling this removes the default.");
      text("env", "Environment variable (optional)", "Enter the variable name, not its value. Priority: explicit argument → environment → default.");
      if (kind === "secret") target.append(el("p", "Secrets cannot have saved defaults. Use an environment variable or PTk’s hidden terminal prompt; do not store a secret here.", { class: "notice" }));
      else if (!value.required) {
        const hasDefault = value.default !== undefined && value.default !== null;
        const enabled = el("input", undefined, { id: `${prefix}-has-default`, type: "checkbox" }); enabled.checked = hasDefault;
        enabled.addEventListener("change", () => {
          defaultModes.delete(JSON.stringify(keys));
          if (!enabled.checked) delete value.default;
          else value.default = kind === "bool" ? false : ["int", "float"].includes(kind) ? 0 : kind === "list" ? [] : kind === "choice" ? value.choices?.[0] || "" : "";
          render();
        });
        add("Use a default value", enabled, "Used only when neither an argument nor the configured environment supplies a value.");
        if (hasDefault) {
          const template = typeof value.default === "string" && value.default.replaceAll("$${", "").includes("${");
          const mode = el("select", undefined, { id: `${prefix}-default-mode` });
          mode.append(el("option", "Literal value", { value: "literal" }), el("option", "PTk variable / template", { value: "template" }));
          // Keep template mode selected while typing even before the opening token is complete.
          const modeKey = JSON.stringify(keys);
          const isTemplate = defaultModes.get(modeKey) ?? template;
          mode.value = isTemplate ? "template" : "literal";
          mode.addEventListener("change", () => { defaultModes.set(modeKey, mode.value === "template"); value.default = mode.value === "template" ? "" : kind === "bool" ? false : ["int", "float"].includes(kind) ? 0 : kind === "list" ? [] : kind === "choice" ? value.choices?.[0] || "" : ""; render(); });
          add("Default source", mode, "Changing this source resets the draft default. Templates are resolved and type-checked when the job runs.");
          let control;
          if (isTemplate) {
            control = el("input", undefined, { id: `${prefix}-default` }); control.value = String(value.default);
            control.addEventListener("input", () => { value.default = control.value; });
          } else if (kind === "list") {
            control = el("textarea", undefined, { id: `${prefix}-default` }); control.value = Array.isArray(value.default) ? value.default.join("\n") : String(value.default);
            control.addEventListener("input", () => { value.default = control.value.split("\n").filter(item => item.length); });
          } else {
            const spec = { type: kind === "bool" ? "boolean" : kind === "int" ? "integer" : kind === "float" ? "number" : "string", ...(kind === "choice" ? { enum: value.choices || [] } : {}) };
            const literal = kind === "bool" ? [true, "true", "1", "yes", "on", "y"].includes(typeof value.default === "string" ? value.default.toLowerCase() : value.default) : ["int", "float"].includes(kind) && Number.isFinite(Number(value.default)) ? Number(value.default) : value.default;
            control = input(literal, spec, next => { value.default = next; }, `${prefix}-default`, [...path, state.name, ...keys, "default"]);
          }
          const row = add(kind === "list" && !isTemplate ? "Default items (one per line)" : "Default value", control);
          if (isTemplate || ["str", "path"].includes(kind)) variables?.(row, control, [...path, state.name, ...keys, "default"]);
        }
      }
      const paramName = keys.length ? String(keys.at(-1)) : state.name;
      const flag = paramName.replaceAll("_", "-");
      const example = kind === "bool" ? `--${flag} / --no-${flag}` : kind === "secret" ? `--${flag} (hidden prompt)` : `--${flag} ${kind === "choice" ? value.choices?.[0] || "VALUE" : kind === "list" ? "item1,item2" : "VALUE"}`;
      target.append(el("p", `Command-line option: ${example}`, { class: "help" }), el("p", "Use in a step: ${params." + paramName + "}", { class: "help" }));
    }
    const defaultModes = new Map();
    function editValue(target, value, field, keys, label, required = false, depth = 0) {
      if (depth > 20) { target.append(el("p", "Use Raw YAML for deeper nesting after creation.", { class: "help" })); return; }
      if (S.resolve(field, schema).title === "ParamSpec" && value && typeof value === "object") { parameterForm(target, value, field, keys); return; }
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
            let next = modeOptions(child).length ? S.stepInitial(child, schema, mode.value) : S.initial(child, schema, { ...context(), name: key, existing: array ? value : [] });
            const declared = S.effective(child, next, schema);
            if (!array && typeof next === "boolean" && typeof declared.default === "boolean" && !(resolved.required || []).includes(key)) next = !declared.default;
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
          name.value = state.name; if (!namedFields) name.placeholder = options.jobChoices ? "JOB or REPO:JOB" : "Choose a descriptive name";
          if (options.jobChoices) {
            const choices = el("datalist", undefined, { id: "workflow-job-choices" });
            options.jobChoices.forEach(job => choices.append(el("option", job, { value: job })));
            name.setAttribute("list", "workflow-job-choices"); node.append(choices);
          }
          name.addEventListener(namedFields ? "change" : "input", () => { state.name = name.value; state.error = ""; if (namedFields) { state.type = ""; state.mode = ""; render(); } });
          node.append(el("label", namedFields ? "Field to add" : options.jobChoices ? "Job (JOB or REPO:JOB)" : "Name", { for: "creation-name" }), name);
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
        node.append(el("p", "Required fields are marked *. Review example commands and paths, then add optional fields as needed. Values remain in this draft until the final confirmation.", { class: "help" }));
        editValue(node, state.draft, chosenSpec(), [], state.name || "New item");
      } else {
        node.append(el("p", "Review the configuration below. The final button saves this draft; it does not run commands or install dependencies. Use Save & validate afterwards for full project checks.", { class: "help" }));
        node.append(el("pre", JSON.stringify(state.draft, null, 2), { class: "creation-preview", "aria-label": "Configuration preview" }));
      }
      const actions = el("div", undefined, { class: "actions creation-actions" });
      actions.append(button("Cancel setup", onCancel));
      if (state.page > (options.editKey !== undefined ? 1 : 0)) actions.append(button("Back", () => { state.page--; state.error = ""; render(); }));
      actions.append(button(state.page === 2 ? options.editKey !== undefined ? "Save parameter" : "Create" : state.page === 1 ? "Review" : "Configure", () => {
        if (state.page === 0) { fieldName(parent, state.name, parentSpec); initialize(); state.page = 1; render(); }
        else if (state.page === 1) { validate(); state.error = ""; state.page = 2; render(); }
        else { validate(); onCreate(options.editKey !== undefined ? options.editKey : fieldName(parent, state.name, parentSpec), structuredClone(state.draft)); }
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
