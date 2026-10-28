"use strict";

// PTK supplies document ownership and schemas. This module applies form edits to
// those documents; it does not discover files or compose configuration.
const YAML = require("yaml");
const model = require("./config-model");
const prefix = (a, b) => a.length <= b.length && a.every((key, i) => key === b[i]);
const at = (value, path) => path.reduce((value, key) => value?.[key], value);
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function writePath(text, path, value, remove = false) {
  const doc = model.parse(text);
  if (!path.length) {
    if (remove) return null;
    doc.contents = doc.createNode(value);
  } else if (remove) {
    if (doc.hasIn(path)) doc.deleteIn(path);
  } else {
    if (!doc.contents) doc.contents = doc.createNode({});
    for (let i = 1; i < path.length; i++) {
      if (!doc.hasIn(path.slice(0, i))) doc.setIn(path.slice(0, i), doc.createNode({}));
    }
    doc.setIn(path, doc.createNode(value));
  }
  return doc.toString({ lineWidth: 0 });
}

function expand(bindings, before, after) {
  return bindings.flatMap(binding => {
    const index = binding.path.indexOf("*");
    if (index < 0) return [binding];
    const container = binding.path.slice(0, index);
    return [...new Set([...Object.keys(at(before, container) || {}), ...Object.keys(at(after, container) || {})])].map(name => {
      if (!/^[A-Za-z][A-Za-z0-9_-]*$/.test(name)) throw new Error("Use an entity name starting with a letter, followed by letters, digits, '_' or '-'.");
      return { ...binding, file: binding.file.replace("{name}", name), path: [...container, name, ...binding.path.slice(index + 1)] };
    });
  });
}

function plan(snapshot, documents, operations) {
  if (!snapshot || snapshot.version !== 2 || !snapshot.bindings || snapshot.value === null) throw new Error("Fix the configuration loading errors before editing the form.");
  const result = new Map(documents);
  let value = snapshot.value;
  for (const operation of operations) {
    model.validatePath(operation.path);
    const path = operation.path;
    if (!path.length) throw new Error("Edit individual configuration fields.");
    if ((snapshot.locked || []).some(locked => prefix(locked, path) || prefix(path, locked))) throw new Error("This field contains precise or complex YAML values. Use Raw YAML to edit it.");
    if (path.length === 3 && path[0] === "variants" && path[1] === "components" && ["remove", "rename"].includes(operation.op)) throw new Error("Add, rename or remove component registrations in Components. Their local definitions stay with the component code.");
    const next = model.inspect(model.edit(YAML.stringify(value), [operation])).value;
    const bindings = expand(snapshot.bindings, value, next);
    const affected = bindings.filter(binding => !equal(at(value, binding.path), at(next, binding.path)));
    function checkOwned(before, after, path = []) {
      if (equal(before, after) || bindings.some(binding => prefix(binding.path, path))) return;
      if (!bindings.some(binding => prefix(path, binding.path))) throw new Error("PTK did not provide a configuration file for this field. Register component directories in project settings first.");
      for (const key of new Set([...Object.keys(before || {}), ...Object.keys(after || {})])) checkOwned(before?.[key], after?.[key], [...path, key]);
    }
    checkOwned(value, next);
    const oldBinding = operation.op === "rename" && bindings.find(binding => equal(binding.path, path) && !binding.document_path.length);
    const renamedText = oldBinding && result.get(oldBinding.file);
    if (!affected.length && !equal(value, next)) throw new Error("PTK did not provide a configuration file for this field. Register component directories in project settings first.");
    for (const binding of affected) {
      const replacement = at(next, binding.path);
      const local = [...binding.document_path, ...path.slice(binding.path.length)];
      const sourceText = result.get(binding.file) || "";
      // In-document edits preserve comments, aliases, scalar spelling and order.
      if (prefix(binding.path, path) && local.length && result.has(binding.file)) {
        result.set(binding.file, model.edit(sourceText, [{ ...operation, path: local }]));
      } else {
        result.set(binding.file, writePath(sourceText, binding.document_path, replacement, replacement === undefined));
      }
    }
    if (operation.op === "rename") {
      const newBinding = bindings.find(binding => equal(binding.path, [...path.slice(0, -1), operation.name]) && !binding.document_path.length);
      if (oldBinding && newBinding && renamedText !== undefined) result.set(newBinding.file, renamedText);
    }
    value = next;
  }
  return new Map([...result].filter(([file, text]) => text !== documents.get(file) && !(text === null && !documents.has(file))));
}

function schemaForFile(snapshot, file) {
  const document = snapshot?.documents?.find(document => {
    if (!document.file.includes("{name}")) return document.file === file;
    const [start, end] = document.file.split("{name}");
    return file.startsWith(start) && file.endsWith(end) && /^[A-Za-z][A-Za-z0-9_-]*$/.test(file.slice(start.length, -end.length));
  });
  return document && { ...document.schema, $defs: snapshot.schema.$defs };
}
function bindingsForFile(snapshot, file) {
  return (snapshot.bindings || []).flatMap(binding => {
    if (!binding.file.includes("{name}")) return binding.file === file ? [binding] : [];
    const [start, end] = binding.file.split("{name}");
    const name = file.slice(start.length, -end.length);
    return file.startsWith(start) && file.endsWith(end) && /^[A-Za-z][A-Za-z0-9_-]*$/.test(name)
      ? [{ ...binding, path: binding.path.map(key => key === "*" ? name : key) }] : [];
  });
}
module.exports = { plan, writePath, schemaForFile, bindingsForFile };
