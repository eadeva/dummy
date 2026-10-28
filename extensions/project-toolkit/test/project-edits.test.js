"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const YAML = require("yaml");
const { plan } = require("../src/project-edits");
const S = require("../media/schema");
const schema = require("../media/config-schema.json");

const source = (path, file) => ({ path, file, line: 1 });
function fixture() {
  return {
    config: { version: 1, entry_file: "/repo/.main.ptk.yml", value: { jobs: { build: { help: "Build", steps: [{ compile: { run: "make" } }] } } }, sources: [
      source([], "/repo/.main.ptk.yml"), source(["jobs"], "/repo/job.ptk.yml"), source(["jobs", "build"], "/repo/job.ptk.yml"), source(["jobs", "build", "help"], "/repo/job.ptk.yml"),
      source(["jobs", "build", "steps"], "/repo/steps.ptk.yml"), source(["jobs", "build", "steps", 0], "/repo/steps.ptk.yml"),
    ] },
    docs: new Map([["/repo/.main.ptk.yml", "repository: {alias: demo, config_path: .}\n"], ["/repo/job.ptk.yml", "# preserve\njobs: {build: {help: Build}}\n"], ["/repo/steps.ptk.yml", "jobs: {build: {steps: [{compile: {run: make}}]}}\n"]]),
  };
}

test("Artifactory event defaults never acquire job step fields", () => {
  const events = S.child(schema.$defs.ArtifactoryStructure, {}, "events", schema);
  assert.deepEqual(S.initial(events, schema), {});
  assert.deepEqual(S.initial(S.child(events, {}, "push", schema), schema), { path: "" });
  assert.deepEqual(S.initial(schema.$defs.JobSpec, schema).steps, [{ step: { run: "echo Hello" } }]);
});

test("ordinary edits update the PTK-recorded file and preserve comments", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["jobs", "build", "help"], value: "New help" }]);
  assert.equal(edits.size, 1);
  assert.match(edits.get("/repo/job.ptk.yml"), /# preserve/);
  assert.equal(YAML.parse(edits.get("/repo/job.ptk.yml")).jobs.build.help, "New help");
});

test("new-file change removes its old definition without moving other fields", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["jobs", "build", "help"], value: "New help" }], "/repo/new.ptk.yml");
  assert.equal(edits.size, 2);
  assert.equal(YAML.parse(edits.get("/repo/job.ptk.yml")).jobs.build.help, undefined);
  assert.equal(YAML.parse(edits.get("/repo/new.ptk.yml")).jobs.build.help, "New help");
  assert.equal(edits.has("/repo/steps.ptk.yml"), false);
});

test("moving a list edit keeps the whole ordered list in one file", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "set", path: ["jobs", "build", "steps", 0, "compile", "run"], value: "make all" }], "/repo/new.ptk.yml");
  assert.equal(YAML.parse(edits.get("/repo/new.ptk.yml")).jobs.build.steps[0].compile.run, "make all");
  assert.equal(YAML.parse(edits.get("/repo/steps.ptk.yml")).jobs.build.steps, undefined);
});

test("renaming a split job updates all source owners without a duplicate", () => {
  const { config, docs } = fixture();
  const edits = plan(config, docs, [{ op: "rename", path: ["jobs", "build"], name: "compile" }], "/repo/new.ptk.yml");
  assert.equal(YAML.parse(edits.get("/repo/new.ptk.yml")).jobs.compile.help, "Build");
  for (const file of ["/repo/job.ptk.yml", "/repo/steps.ptk.yml"]) assert.equal(YAML.parse(edits.get(file)).jobs, undefined);
});
