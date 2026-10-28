/* Field capabilities and names come exclusively from the installed PTK. */
(function (root, factory) {
  if (typeof module === "object") module.exports = factory();
  else root.PtkVariables = factory();
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  function context(schema, value, path, S) {
    const root = schema;
    let found;
    for (let i = 0; i <= path.length; i++) {
      const node = S.effective(schema, value, root);
      if (node["x-ptk-template-context"]) found = node["x-ptk-template-context"];
      if (i < path.length) { schema = S.child(schema, value, path[i], root); value = value?.[path[i]]; }
    }
    return found;
  }
  function available(state, schema, path, S) {
    if (state.variables?.version !== 1) return [];
    const scope = context(schema, state.value, path, S);
    if (!scope) return [];
    let logical = path;
    if (!state.logical) {
      const binding = state.pathBindings?.find(item => item.document_path.every((key, i) => path[i] === key));
      if (!binding) return [];
      logical = [...binding.path, ...path.slice(binding.document_path.length)];
    }
    const job = logical[0] === "jobs" ? logical[1] : undefined;
    return state.variables.entries.filter(entry => entry.contexts.includes(scope) && (!entry.job || entry.job === job));
  }
  function token(value, caret) {
    const before = value.slice(0, caret);
    const start = before.lastIndexOf("${");
    if (start < 0 || before[start - 1] === "$" || /[{}\s]/.test(before.slice(start + 2))) return undefined;
    const closing = value.indexOf("}", caret);
    const tail = closing < 0 ? "" : value.slice(caret, closing);
    return { start, end: closing >= 0 && !/[{}\s]/.test(tail) ? closing + 1 : caret, query: before.slice(start + 2) };
  }
  function filter(entries, query) {
    const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    return entries.filter(entry => words.every(word => `${entry.reference} ${entry.group} ${entry.description}`.toLowerCase().includes(word)))
      .sort((a, b) => a.group.localeCompare(b.group) || a.reference.localeCompare(b.reference));
  }
  return { available, token, filter };
});
