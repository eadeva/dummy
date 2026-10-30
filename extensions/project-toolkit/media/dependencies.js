/* Graph editing rules shared by the webview and the YAML writer. */
(function (root, factory) {
  if (typeof module === "object") module.exports = factory();
  else root.PtkDependencies = factory();
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const at = (value, path) => path.reduce((value, key) => value?.[key], value);
  const targetKey = (target, owner) => target.includes(":") ? target : `${owner || ""}:${target}`;
  function availableJobs(configuration, invocations, current) {
    const owner = configuration?.repository?.alias;
    const used = new Set(Object.entries(invocations || {}).filter(([id, call]) => id !== current && typeof call?.job === "string").map(([, call]) => targetKey(call.job, owner)));
    return Object.keys(configuration?.jobs || {}).filter(job => !used.has(targetKey(job, owner)));
  }
  function validateTargets(invocations, owner) {
    const seen = new Map();
    for (const [id, call] of Object.entries(invocations || {})) {
      if (typeof call?.job !== "string") continue;
      const key = targetKey(call.job, owner);
      if (seen.has(key)) throw new Error(`Job ${call.job} can only be chosen once per workflow; ${seen.get(key)} and ${id} refer to it.`);
      seen.set(key, id);
    }
  }
  function nodes(value) {
    if (!object(value)) throw new Error("The dependency graph must be a named mapping.");
    return Object.entries(value).map(([id, item]) => {
      if (!object(item)) throw new Error(`${id}: the definition must be a mapping. Use the fields below to correct it.`);
      const needs = typeof item.needs === "string" ? [item.needs] : item.needs ?? [];
      if (item.needs === null || !Array.isArray(needs) || needs.some(need => typeof need !== "string")) throw new Error(`${id}: needs must be a name or list of names. Use the fields below to correct it.`);
      return { id, needs, label: typeof item.job === "string" ? item.job : typeof item.title === "string" ? item.title : "" };
    });
  }
  function validate(entries) {
    const byId = new Map(entries.map(node => [node.id, node]));
    const degree = new Map(), dependents = new Map(entries.map(node => [node.id, []]));
    for (const node of entries) {
      if (new Set(node.needs).size !== node.needs.length) throw new Error(`${node.id}: duplicate prerequisites.`);
      degree.set(node.id, node.needs.length);
      for (const need of node.needs) {
        if (need === node.id) throw new Error("A node cannot depend on itself.");
        if (!byId.has(need)) throw new Error(`${node.id}: unknown prerequisite ${need}.`);
        dependents.get(need).push(node.id);
      }
    }
    const ready = entries.filter(node => !node.needs.length).map(node => node.id);
    for (let i = 0; i < ready.length; i++) for (const next of dependents.get(ready[i])) {
      degree.set(next, degree.get(next) - 1);
      if (!degree.get(next)) ready.push(next);
    }
    if (ready.length !== entries.length) throw new Error("This connection would create a dependency cycle.");
  }
  function update(value, from, to, remove = false) {
    if (typeof from !== "string" || typeof to !== "string" || typeof remove !== "boolean") throw new Error("Invalid dependency edit.");
    const entries = nodes(value), target = entries.find(node => node.id === to);
    if (!target) throw new Error("The dependent no longer exists.");
    if (remove) {
      if (!target.needs.includes(from)) throw new Error("The connection no longer exists.");
      // Removal may repair an invalid imported graph one edge at a time.
      return target.needs.filter(id => id !== from);
    }
    if (!entries.some(node => node.id === from)) throw new Error("The prerequisite no longer exists.");
    if (target.needs.includes(from)) throw new Error("This connection already exists.");
    const needs = [...target.needs, from];
    validate(entries.map(node => node === target ? { ...node, needs } : node));
    return needs;
  }
  function context(schema, value, selected, S) {
    for (let length = 0; length <= selected.length; length++) {
      const path = selected.slice(0, length), current = at(value, path);
      const spec = S.effective(S.at(schema, value, path, schema), current, schema);
      if (spec["x-ptk-graph"]) return { path, kind: spec["x-ptk-graph"], value: current, selected: selected[length] };
    }
    const current = at(value, selected);
    const spec = S.effective(S.at(schema, value, selected, schema), current, schema);
    for (const [key, child] of Object.entries(spec.properties || {})) {
      const kind = S.resolve(child, schema)["x-ptk-graph"];
      if (kind && object(current?.[key])) return { path: [...selected, key], kind, value: current[key] };
    }
  }
  return { nodes, validate, update, context, targetKey, availableJobs, validateTargets };
});
