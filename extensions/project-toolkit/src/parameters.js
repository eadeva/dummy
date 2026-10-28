"use strict";

function validateParameters(specs, values) {
  if (!values || typeof values !== "object" || Array.isArray(values)) throw new Error("Invalid parameter values.");
  const allowed = specs.filter(spec => spec.type !== "secret");
  for (const key of Object.keys(values)) {
    const spec = allowed.find(item => item.name === key);
    if (!spec || typeof values[key] !== "string") throw new Error(`Unsupported parameter: ${key}`);
    const value = values[key];
    if (spec.required && !value.trim()) throw new Error(`${key}: enter a value.`);
    if (spec.type === "bool" && !["true", "false"].includes(value)) throw new Error(`${key}: select true or false.`);
    if (spec.type === "int" && !/^[+-]?\d+$/.test(value)) throw new Error(`${key}: enter a whole number.`);
    if (spec.type === "float" && (!value.trim() || !Number.isFinite(Number(value)))) throw new Error(`${key}: enter a number.`);
    if (spec.type === "choice" && !spec.choices.includes(value)) throw new Error(`${key}: select one of the available choices.`);
  }
  for (const spec of allowed) {
    if (spec.required && !spec.env && !Object.hasOwn(values, spec.name)) throw new Error(`${spec.name}: enter a value.`);
  }
  return values;
}

module.exports = { validateParameters };
