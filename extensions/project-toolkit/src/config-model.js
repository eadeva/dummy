"use strict";

const YAML = require("yaml");
const forbidden = new Set(["__proto__", "prototype", "constructor"]);

// Use PyYAML's scalar spelling rules. YAML 1.1 implementations differ on y/n,
// leading zeroes and exponent notation; those differences must not turn an
// untouched string into a boolean or number when another field is edited.
function ptkTags(tags) {
  return tags.map(original => {
    const tag = { ...original };
    if (tag.tag === "tag:yaml.org,2002:bool") {
      tag.test = tag.test.test("true") ? /^(?:true|True|TRUE|yes|Yes|YES|on|On|ON)$/ : /^(?:false|False|FALSE|no|No|NO|off|Off|OFF)$/;
    } else if (tag.tag === "tag:yaml.org,2002:int") {
      if (!tag.format) tag.test = /^[-+]?(?:0|[1-9][0-9_]*)$/;
      if (tag.format === "TIME") tag.test = /^[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+$/;
    } else if (tag.tag === "tag:yaml.org,2002:float") {
      if (tag.format === "EXP") tag.test = /^(?:[-+]?[0-9][0-9_]*\.[0-9_]*|\.[0-9][0-9_]*)[eE][-+][0-9]+$/;
      else if (!tag.format && tag.test.test("1.0")) tag.test = /^(?:[-+]?[0-9][0-9_]*\.[0-9_]*|\.[0-9][0-9_]*)$/;
      tag.stringify = (...args) => original.stringify(...args).replace(/^([-+]?\d+)(e[-+]\d+)$/i, "$1.0$2");
    }
    return tag;
  });
}

function parse(text) {
  const doc = YAML.parseDocument(text, {
    version: "1.1", schema: "yaml-1.1", intAsBigInt: true,
    keepSourceTokens: true, uniqueKeys: true, customTags: ptkTags,
  });
  if (doc.errors.length) throw new Error(doc.errors.map(error => error.message).join("\n"));
  return doc;
}

// Read authored nodes, not resolved includes or expanded aliases. Editing a file
// must never copy an included file's values into the including document.
function inspect(text) {
  const doc = parse(text);
  const locked = [];
  const annotations = [];
  function visit(node, path = []) {
    if (YAML.isAlias(node)) {
      locked.push(path);
      return `*${node.source}`;
    }
    if (node?.tag) {
      annotations.push({ path, text: node.tag });
      if (!["!append", "!replace"].includes(node.tag) && !node.tag.startsWith("tag:yaml.org,2002:")) locked.push(path);
    }
    if (YAML.isMap(node)) {
      const value = Object.create(null);
      for (const pair of node.items) {
        if (!YAML.isScalar(pair.key) || typeof pair.key.value !== "string" && pair.key.source !== "<<" || forbidden.has(pair.key.value)) {
          locked.push(path);
          return "This mapping uses complex keys. Open Raw YAML to edit it.";
        }
        const key = pair.key.source === "<<" ? "<<" : pair.key.value;
        if (key === "<<") locked.push([...path, key]);
        value[key] = visit(pair.value, [...path, key]);
      }
      return value;
    }
    if (YAML.isSeq(node)) return node.items.map((item, index) => visit(item, [...path, index]));
    const value = node?.value ?? null;
    if (typeof value === "bigint") {
      if (value >= BigInt(Number.MIN_SAFE_INTEGER) && value <= BigInt(Number.MAX_SAFE_INTEGER)) return Number(value);
      locked.push(path);
      return String(value);
    }
    if (value instanceof Date || typeof value === "number" && (!Number.isFinite(value) || Number.isInteger(value) && !Number.isSafeInteger(value))) {
      locked.push(path);
      return node.source || String(value);
    }
    return value;
  }
  return { value: doc.contents ? visit(doc.contents) : {}, locked, annotations };
}

function validatePath(path) {
  if (!Array.isArray(path) || path.length > 100 || path.some(key =>
    !(typeof key === "string" && !forbidden.has(key) || Number.isSafeInteger(key) && key >= 0))) {
    throw new Error("Invalid configuration field path.");
  }
}

function validateValue(value, depth = 0) {
  if (depth > 100) throw new Error("Configuration value is too deeply nested.");
  if (value === null || ["string", "boolean"].includes(typeof value)) return;
  if (typeof value === "number" && Number.isFinite(value)) {
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) throw new Error("Use Raw YAML for integers outside the form's precise numeric range.");
    return;
  }
  if (Array.isArray(value)) { value.forEach(item => validateValue(item, depth + 1)); return; }
  if (value && typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype) {
    for (const [key, item] of Object.entries(value)) {
      if (forbidden.has(key)) throw new Error("Unsupported configuration key.");
      validateValue(item, depth + 1);
    }
    return;
  }
  throw new Error("Invalid configuration field value.");
}

function edit(text, operations) {
  if (!Array.isArray(operations) || !operations.length || operations.length > 100) throw new Error("Invalid configuration edit.");
  const doc = parse(text);
  for (const operation of operations) {
    const { op, path } = operation;
    validatePath(path);
    if (!path.length) throw new Error("Use individual fields or Raw YAML to change the document root.");
    const state = inspect(doc.toString());
    if (state.locked.some(prefix => prefix.length <= path.length && prefix.every((key, i) => key === path[i]))) {
      throw new Error("This field is an alias, include or complex YAML value. Use Raw YAML to edit it.");
    }
    if (!doc.contents && op === "add" && path.length === 1) doc.contents = doc.createNode({});
    const parent = doc.getIn(path.slice(0, -1), true);
    const key = path.at(-1);
    if (!YAML.isMap(parent) && !YAML.isSeq(parent)) throw new Error("The parent field no longer exists.");
    if (YAML.isSeq(parent) && (!Number.isInteger(key) || key > parent.items.length)) throw new Error("Invalid list position.");
    if (YAML.isMap(parent) && typeof key !== "string") throw new Error("Invalid field name.");
    const exists = parent.has(key);
    if (op === "add") {
      if (exists) throw new Error(`Field ${key} already exists.`);
      validateValue(operation.value);
      parent.set(key, doc.createNode(operation.value));
    } else {
      if (!exists) throw new Error(`Field ${key} no longer exists.`);
      if (op === "remove") parent.delete(key);
      else if (op === "rename") {
        if (!YAML.isMap(parent) || typeof operation.name !== "string" || !operation.name.trim() || forbidden.has(operation.name)) throw new Error("Invalid field name.");
        if (parent.has(operation.name)) throw new Error(`Field ${operation.name} already exists.`);
        parent.items.find(pair => pair.key.value === key).key.value = operation.name;
      } else if (op === "move") {
        const next = key + operation.direction;
        if (!YAML.isSeq(parent) || ![-1, 1].includes(operation.direction) || next < 0 || next >= parent.items.length) throw new Error("Invalid list move.");
        [parent.items[key], parent.items[next]] = [parent.items[next], parent.items[key]];
      } else if (op === "set") {
        validateValue(operation.value);
        const current = parent.get(key, true);
        if (YAML.isScalar(current) && (operation.value === null || typeof operation.value !== "object")) current.value = operation.value;
        else {
          const next = doc.createNode(operation.value);
          for (const property of ["comment", "commentBefore", "spaceBefore", "anchor", "tag"]) {
            if (current?.[property] !== undefined) next[property] = current[property];
          }
          parent.set(key, next);
        }
      } else throw new Error("Unsupported configuration edit.");
    }
  }
  const indent = text.match(/\n( +)\S/)?.[1].length || 2;
  let result = doc.toString({ indent: Math.min(indent, 8), lineWidth: 0 });
  if (text.includes("\r\n")) result = result.replace(/\n/g, "\r\n");
  if (text.startsWith("\uFEFF") && !result.startsWith("\uFEFF")) result = "\uFEFF" + result;
  return result;
}

function minimalEdit(before, after) {
  let start = 0;
  while (start < before.length && start < after.length && before[start] === after[start]) start++;
  let end = before.length;
  let afterEnd = after.length;
  while (end > start && afterEnd > start && before[end - 1] === after[afterEnd - 1]) { end--; afterEnd--; }
  return { start, end, text: after.slice(start, afterEnd) };
}

module.exports = { inspect, edit, minimalEdit, validatePath };
