"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const YAML = require("yaml");
const { plan, schemaForFile } = require("../src/project-edits");
const S = require("../media/schema");
const schema = require("../media/config-schema.json");
function fixture() {
  return {
    config: { version: 3, value: { project: { name: "demo" }, jobs: { build: { help: "Build", steps: {compile: { run: "make" }} } } }, bindings: [
      { file: "/repo/config/jobs/{name}.ptk.yml", path: ["jobs", "*"], document_path: [] },
      { file: "/repo/config/project.ptk.yml", path: ["project", "name"], document_path: ["name"] },
    ] },
    docs: new Map([["/repo/config/project.ptk.yml", "name: demo\n"], ["/repo/config/jobs/build.ptk.yml", "# preserve\nhelp: Build\nsteps: {compile: {run: make}}\n"]]),
  };
}

test("Artifactory event defaults never acquire job step fields", () => {
  const events = S.child(schema.$defs.ArtifactoryStructure, {}, "events", schema);
  assert.deepEqual(S.initial(events, schema), { push: { path: "" } });
  assert.deepEqual(S.initial(S.child(events, {}, "push", schema), schema), { path: "" });
});
test("scalar edits use document-relative paths and preserve comments", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["jobs", "build", "help"], value: "New help" }]);
  assert.equal(edits.size, 1);
  const text = edits.get("/repo/config/jobs/build.ptk.yml");
  assert.match(text, /# preserve/);
  assert.equal(YAML.parse(text).help, "New help");
  assert.equal(YAML.parse(text).jobs, undefined);
});
test("project fields are written without a project wrapper", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["project", "name"], value: "new" }]);
  assert.deepEqual(YAML.parse(edits.get("/repo/config/project.ptk.yml")), { name: "new" });
});
test("new jobs create their conventional document", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "add", path: ["jobs", "check"], value: { steps: {lint: { run: "ruff" }} } }]);
  assert.equal(edits.size, 1);
  assert.equal(YAML.parse(edits.get("/repo/config/jobs/check.ptk.yml")).steps.lint.run, "ruff");
});
test("removing an entity deletes its document", () => {
  const { config, docs } = fixture();
  assert.equal(plan(config, docs, [{ op: "remove", path: ["jobs", "build"] }]).get("/repo/config/jobs/build.ptk.yml"), null);
});
test("renaming an entity moves its body and comments", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "rename", path: ["jobs", "build"], name: "compile" }]);
  assert.equal(edits.get("/repo/config/jobs/build.ptk.yml"), null);
  assert.equal(edits.get("/repo/config/jobs/compile.ptk.yml"), docs.get("/repo/config/jobs/build.ptk.yml"));
});
test("entity filenames cannot escape their conventional directory", () => {
  const { config, docs } = fixture();
  assert.throws(() => plan(config, docs, [{ op: "rename", path: ["jobs", "build"], name: "../escape" }]), /entity name/);
});
test("list edits stay in the entity document", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["jobs", "build", "steps", "compile", "run"], value: "make all" }]);
  assert.equal(YAML.parse(edits.get("/repo/config/jobs/build.ptk.yml")).steps.compile.run, "make all");
});
test("component features use the exact file provided by PTK", () => {
  const config = { version: 3, value: { variants: { components: { networking: {} } } }, bindings: [{ file: "/repo/src/net/component.variants.ptk.yml", path: ["variants", "components", "networking"], document_path: [] }] };
  const edits = plan(config, new Map(), [{ op: "add", path: ["variants", "components", "networking", "features"], value: { TLS: { type: "bool" } } }]);
  assert.deepEqual(YAML.parse(edits.get("/repo/src/net/component.variants.ptk.yml")), { features: { TLS: { type: "bool" } } });
});
test("raw forms use the installed schema for that document", () => {
  const config = { schema, documents: [{ file: "/repo/jobs/{name}.ptk.yml", schema: { $ref: "#/$defs/JobSpec" } }] };
  assert.equal(schemaForFile(config, "/repo/jobs/build.ptk.yml").$ref, "#/$defs/JobSpec");
  assert.equal(schemaForFile(config, "/repo/jobs/nested/build.ptk.yml"), undefined);
});
test("renaming after a pending scalar edit preserves that edit", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["jobs", "build", "help"], value: "Updated" }, { op: "rename", path: ["jobs", "build"], name: "compile" }]);
  assert.equal(YAML.parse(edits.get("/repo/config/jobs/compile.ptk.yml")).help, "Updated");
});
test("unowned fields cannot be silently discarded when editing a parent", () => {
  const { config, docs } = fixture();
  assert.throws(() => plan(config, docs, [{ op: "set", path: ["project"], value: { name: "demo", unknown: 1 } }]), /provide a configuration file/);
});
