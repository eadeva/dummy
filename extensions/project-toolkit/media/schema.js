/* Shared schema traversal for the form and its regression tests. */
(function (root, factory) {
  if (typeof module === "object") module.exports = factory();
  else root.PtkSchema = factory();
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const type = value => value === null ? "null" : Array.isArray(value) ? "array" : typeof value === "number" ? Number.isInteger(value) ? "integer" : "number" : typeof value;
  function resolve(schema, root) {
    if (!schema || typeof schema !== "object") return {};
    if (!schema.$ref) return schema;
    const target = schema.$ref.split("/").slice(1).reduce((value, key) => value?.[key], root);
    return { ...target, ...schema, $ref: undefined };
  }
  function choices(schema, root) {
    schema = resolve(schema, root);
    return (schema.anyOf || schema.oneOf || [schema]).map(part => resolve(part, root));
  }
  function effective(schema, value, root) {
    const outer = resolve(schema, root);
    const variants = choices(schema, root);
    const match = variants.find(part => part.type === type(value) || part.type === "number" && type(value) === "integer");
    const chosen = match || variants.find(part => part.type !== "null") || {};
    return { ...outer, ...chosen, ...(outer.description ? { description: outer.description } : {}) };
  }
  function help(schema, value, root) {
    const spec = effective(schema, value, root);
    const details = [];
    const types = [...new Set(choices(schema, root).map(item => item.type).filter(Boolean))];
    if (types.length) details.push(`Type: ${types.join(" / ")}`);
    if (Object.hasOwn(spec, "default")) details.push(`Default: ${JSON.stringify(spec.default)}`);
    if (spec.enum) details.push(`Values: ${spec.enum.join(", ")}`);
    for (const [key, label] of [["minimum", "Minimum"], ["maximum", "Maximum"], ["exclusiveMinimum", "Greater than"], ["minLength", "Minimum characters"], ["minItems", "Minimum items"], ["pattern", "Pattern"]]) {
      if (spec[key] !== undefined) details.push(`${label}: ${spec[key]}`);
    }
    return [spec.description, details.join(" · ")].filter(Boolean).join("\n");
  }
  function child(schema, value, key, root) {
    schema = effective(schema, value, root);
    return schema.type === "array" || Array.isArray(value) ? schema.items || {}
      : schema.properties?.[key] || (typeof schema.additionalProperties === "object" ? schema.additionalProperties : {});
  }
  function at(schema, value, path, root) {
    for (const key of path) { schema = child(schema, value, key, root); value = value?.[key]; }
    return schema;
  }
  function orderedEntries(schema, value, root, { includeMissing = false } = {}) {
    const entries = Object.entries(value || {});
    // Lists are execution/data order, never a presentation sort.
    if (Array.isArray(value)) return entries;
    const spec = effective(schema, value, root);
    if (includeMissing) for (const key of Object.keys(spec.properties || {})) {
      if (!Object.hasOwn(value || {}, key)) entries.push([key, undefined]);
    }
    const order = spec["x-ptk-field-order"] || Object.keys(spec.properties || {});
    const ranks = new Map(order.map((key, index) => [key, index]));
    const nested = ([key, current]) => current === undefined
      ? choices(child(schema, value, key, root), root).some(item => ["object", "array"].includes(item.type))
      : current !== null && typeof current === "object";
    return entries.sort((a, b) => Number(nested(a)) - Number(nested(b)) || (ranks.get(a[0]) ?? order.length) - (ranks.get(b[0]) ?? order.length));
  }
  function initial(schema, root, context = {}) {
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    const uniqueName = (base, used) => {
      let name = base, index = 2;
      while (used.has(name)) name = `${base}_${index++}`;
      return name;
    };
    function create(spec, seed, depth = 0, existing = []) {
      if (depth > 30) throw new Error("This schema requires a recursive value. Use Raw YAML to define it.");
      spec = resolve(spec, root);
      const template = spec["x-ptk-initial"] ?? (spec.default !== null ? spec.default : undefined);
      let value = structuredClone(seed === undefined ? template : seed);
      const variants = choices(spec, root);
      const chosen = variants.find(part => value !== undefined && part.type === type(value)) || variants.find(part => part.type !== "null") || spec;
      spec = { ...spec, ...chosen };
      if ((value === undefined || object(value) && !Object.keys(value).length) && spec["x-ptk-initial"] !== undefined) value = structuredClone(spec["x-ptk-initial"]);
      if (value === undefined && spec.default !== undefined && spec.default !== null) value = structuredClone(spec.default);
      if (Object.hasOwn(spec, "const")) return structuredClone(spec.const);
      const reference = spec["x-ptk-reference"];
      if (reference && context.configuration) {
        const targets = reference.path.reduce((value, key) => value?.[key], context.configuration);
        const names = Object.keys(targets || {});
        if (!names.length) throw new Error(`Create a ${reference.label} before adding this field.`);
        return names.includes(value) ? value : names[0];
      }
      if (spec.enum) return spec.enum.includes(value) ? value : structuredClone(spec.enum[0]);
      if (spec.type === "object" || object(value)) {
        value = object(value) ? value : {};
        for (const key of new Set([...(spec.required || []), ...Object.keys(value)])) {
          const property = spec.properties?.[key] || (object(spec.additionalProperties) ? spec.additionalProperties : {});
          value[key] = create(property, value[key], depth + 1);
        }
        while (Object.keys(value).length < (spec.minProperties || 0)) {
          const unused = [...Object.keys(spec.properties || {}), ...(spec.propertyNames?.enum || [])].find(key => !Object.hasOwn(value, key));
          if (!unused && spec.additionalProperties === false) throw new Error("The schema cannot supply enough required fields.");
          const key = unused || uniqueName(spec["x-ptk-entry-name"] || "item", new Set(Object.keys(value)));
          value[key] = create(spec.properties?.[key] || spec.additionalProperties, undefined, depth + 1);
        }
        if (spec["x-ptk-entry-name"] && spec.maxProperties === 1 && Object.keys(value).length === 1) {
          const key = Object.keys(value)[0];
          const name = uniqueName(key, new Set(existing.flatMap(item => object(item) ? Object.keys(item) : [])));
          if (name !== key) value = { [name]: value[key] };
        }
        return value;
      }
      if (spec.type === "array" || Array.isArray(value)) {
        const result = [];
        const items = Array.isArray(value) ? value : [];
        for (let index = 0; index < Math.max(items.length, spec.minItems || 0); index++) result.push(create(spec.items, items[index], depth + 1, result));
        return result;
      }
      if (value !== undefined) return value;
      if (spec.type === "boolean") return false;
      if (["number", "integer"].includes(spec.type)) return spec.minimum ?? (spec.exclusiveMinimum !== undefined ? spec.exclusiveMinimum + 1 : Math.min(0, spec.maximum ?? 0));
      if (spec.minLength) return "value".repeat(Math.ceil(spec.minLength / 5)).slice(0, spec.minLength);
      return spec.type === "null" ? null : "";
    }
    return create(schema, undefined, 0, context.existing || []);
  }
  return { type, resolve, choices, effective, help, child, at, orderedEntries, initial };
});
