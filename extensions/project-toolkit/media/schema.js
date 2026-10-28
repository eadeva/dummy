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
    const variants = choices(schema, root);
    const match = variants.find(part => part.type === type(value) || part.type === "number" && type(value) === "integer");
    return { ...resolve(schema, root), ...(match || variants.find(part => part.type !== "null") || {}) };
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
  function initial(schema, root, depth = 0) {
    schema = resolve(schema, root);
    if (depth > 15) return null;
    // A non-null field is useful when adding an optional field; absence already
    // represents the default null. Defaults never populate unselected fields.
    if (Object.hasOwn(schema, "default") && schema.default !== null) return structuredClone(schema.default);
    const chosen = choices(schema, root).find(part => part.type !== "null") || schema;
    if (Object.hasOwn(chosen, "default") && chosen.default !== null) return structuredClone(chosen.default);
    if (Object.hasOwn(chosen, "const")) return structuredClone(chosen.const);
    if (chosen.enum) return chosen.enum[0];
    if (chosen.type === "object") {
      const value = {};
      for (const key of chosen.required || []) value[key] = initial(chosen.properties?.[key], root, depth + 1);
      if (!Object.keys(value).length && chosen.minProperties) value.step = { run: "echo Hello" };
      return value;
    }
    if (chosen.type === "array") return Array.from({ length: chosen.minItems || 0 }, () => initial(chosen.items, root, depth + 1));
    if (chosen.type === "boolean") return false;
    if (["number", "integer"].includes(chosen.type)) return chosen.minimum ?? (chosen.exclusiveMinimum !== undefined ? chosen.exclusiveMinimum + 1 : 0);
    return chosen.type === "null" ? null : "";
  }
  function infer(value, filename = "") {
    if (Array.isArray(value)) return "steps";
    if (value && ("components" in value || "constraints" in value || "default" in value && "variants" in value) || /variants?\.ptk\.ya?ml$/i.test(filename) && !value?.project) return "ProductLineSpec";
    return "configuration";
  }
  function rootSchema(schema, kind) {
    if (kind === "configuration") return schema;
    if (kind === "steps") return { type: "array", items: { $ref: "#/$defs/StepEntry" } };
    return { $ref: `#/$defs/${kind}` };
  }
  return { type, resolve, choices, effective, child, at, initial, infer, rootSchema };
});
