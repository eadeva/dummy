/* Labels shared by the VS Code tree and configuration form. */
(function (root, factory) {
  if (typeof module === "object") module.exports = factory();
  else root.PtkPresentation = factory();
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const compact = value => String(value).replace(/\s+/g, " ").trim().slice(0, 90);
  function listLabel(value) {
    if (Array.isArray(value)) return value.map(item => object(item) ? listLabel(item) : compact(item)).join(" · ").slice(0, 90) || "Empty list";
    if (!object(value)) return value === null ? "Not set" : compact(value) || "Empty value";
    for (const key of ["name", "id", "job", "uses", "path", "run", "description"]) {
      if (typeof value[key] === "string" && value[key].trim()) return compact(value[key]);
      if (key === "run" && Array.isArray(value[key])) return compact(value[key].join(" "));
    }
    return Object.keys(value).join(" · ") || "Empty entry";
  }
  function pathLabel(value, path) {
    const key = path.at(-1);
    const item = path.reduce((current, part) => current?.[part], value);
    return typeof key === "number" ? listLabel(item, path) : key ?? "Configuration";
  }
  const sections = {
    repository: "repo", project: "project", jobs: "tasklist", workflows: "git-merge",
    variants: "layers", tools: "tools", credentials: "key", environment: "terminal",
    vars: "symbol-variable", params: "settings-gear", param_defaults: "settings-gear",
    artifactory: "package", events: "calendar", versioning: "versions", configs: "settings-gear",
    layout: "folder", logging_history_backups: "history", report_formats: "graph", log_analysis: "search", steps: "git-merge",
  };
  function icon(value, path) {
    if (!path.length) return "settings-gear";
    if (path.length === 1 && sections[path[0]]) return sections[path[0]];
    if (path.length === 2 && path[0] === "jobs") return "play-circle";
    if (path.length === 2 && path[0] === "workflows") return "git-merge";
    if (path.at(-2) === "events") return "calendar";
    if (path.at(-2) === "steps") return "terminal";
    if (path.at(-1) === "steps") return "git-merge";
    if (Array.isArray(value)) return "list-unordered";
    return object(value) ? "symbol-object" : undefined;
  }
  return { listLabel, pathLabel, icon };
});
