"use strict";

// Transform PTK's authored snapshot. Discovery and composition belong to PTK;
// this module only routes requested edits back to their recorded source files.
const YAML = require("yaml");
const model = require("./config-model");
const prefix = (a, b) => a.length <= b.length && a.every((key, i) => key === b[i]);
const at = (value, path) => path.reduce((value, key) => value?.[key], value);

function writePath(text, path, value, remove = false) {
  const doc = model.parse(text);
  if (remove) {
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

function plan(snapshot, documents, operations, destination) {
  if (!snapshot || snapshot.version !== 1 || snapshot.value === null) throw new Error("Fix the configuration loading errors before editing the merged form.");
  const result = new Map(documents);
  let value = snapshot.value;
  for (const operation of operations) {
    model.validatePath(operation.path);
    const path = operation.path;
    if (!path.length) throw new Error("Edit individual configuration fields.");
    if (destination && ["repository", "virtual_monorepo"].includes(path[0])) throw new Error("Project metadata must remain in .main.ptk.yml.");
    // Validate the operation against the authoritative logical value. This is
    // an edit, not another load/merge implementation.
    const next = model.inspect(model.edit(YAML.stringify(value), [operation])).value;
    let atomicPath = path.some(key => typeof key === "number")
      ? path.slice(0, path.findIndex(key => typeof key === "number")) : path;
    if (operation.op === "rename") atomicPath = path.slice(0, -1);
    if (!atomicPath.length) throw new Error("Use Raw YAML to rename a top-level schema field.");
    if ((snapshot.locked || []).some(locked => prefix(locked, atomicPath) || prefix(atomicPath, locked))) throw new Error("This field contains precise or complex YAML values. Use Raw YAML to edit or move it.");
    const owners = snapshot.sources.filter(source => prefix(atomicPath, source.path));
    const files = [...new Set(owners.map(source => source.file))];
    const nearest = snapshot.sources.filter(source => prefix(source.path, atomicPath)).sort((a, b) => b.path.length - a.path.length)[0];
    const target = destination || nearest?.file || snapshot.entry_file;
    if (!target) throw new Error("PTK did not provide a source file for this field.");
    if (!destination && files.length <= 1 && (!files.length || files[0] === target) && result.has(target)) {
      // Preserve source comments, quotes and anchors for normal edits.
      let text = result.get(target);
      if (operation.op === "add") {
        const doc = model.parse(text);
        for (let i = 1; i < path.length; i++) {
          if (!doc.hasIn(path.slice(0, i))) doc.setIn(path.slice(0, i), doc.createNode({}));
        }
        text = doc.toString({ lineWidth: 0 });
      }
      result.set(target, model.edit(text, [operation]));
    } else {
      // Lists are atomic. A change to a split object removes every old
      // contribution before writing its replacement into the chosen file.
      for (const file of files) {
        if (!result.has(file)) throw new Error(`Source file is unavailable: ${file}`);
        result.set(file, writePath(result.get(file), atomicPath, undefined, true));
      }
      const replacement = at(next, atomicPath);
      if (replacement !== undefined) result.set(target, writePath(result.get(target) || "", atomicPath, replacement));
    }
    value = next;
  }
  return new Map([...result].filter(([file, text]) => text !== documents.get(file)));
}

module.exports = { plan, writePath };
