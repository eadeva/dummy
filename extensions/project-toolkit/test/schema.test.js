"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../media/schema");
const schema = require("../media/config-schema.json");

test("field ordering survives alphabetized JSON and keeps scalars before nested values", () => {
  function alphabetize(value) {
    return Array.isArray(value) ? value.map(alphabetize) : value && typeof value === "object"
      ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, child]) => [key, alphabetize(child)])) : value;
  }
  const sorted = alphabetize(schema);
  const job = { steps: [{ z: "first" }, { a: "second" }], env: {}, audience: "all", help: "Build" };
  assert.deepEqual(S.orderedEntries(sorted.$defs.JobSpec, job, sorted).map(([key]) => key), ["help", "audience", "env", "steps"]);
  assert.deepEqual(S.orderedEntries(sorted, { workflows: {}, project: {}, artifactory: {}, jobs: {}, repository: {}, ptk_version: ">=1" }, sorted).map(([key]) => key), ["ptk_version", "repository", "project", "jobs", "workflows", "artifactory"]);
  const steps = S.at(sorted, { jobs: { build: job } }, ["jobs", "build", "steps"], sorted);
  assert.deepEqual(S.orderedEntries(steps, job.steps, sorted), [["0", job.steps[0]], ["1", job.steps[1]]]);
  assert.deepEqual(Object.keys(job), ["steps", "env", "audience", "help"], "presentation does not mutate the configuration");
});

test("ordering handles missing optional fields, references, null and dictionaries", () => {
  const properties = { nested: { $ref: "#/$defs/Child" }, nullable: { anyOf: [{ type: "object" }, { type: "null" }] }, scalar: { type: "string" } };
  const spec = { type: "object", properties, "x-ptk-field-order": ["nested", "nullable", "scalar"], $defs: { Child: { type: "object" } } };
  assert.deepEqual(S.orderedEntries(spec, { nullable: null }, spec, { includeMissing: true }).map(([key]) => key), ["nullable", "scalar", "nested"]);
  assert.deepEqual(S.orderedEntries({}, { z: "first", a: "second", group: {} }, {}).map(([key]) => key), ["z", "a", "group"]);
});

test("field help preserves context through references and includes defaults and limits", () => {
  const root = { $defs: { Nested: { type: "object", description: "Generic model help" } } };
  const spec = { description: "Purpose of this field", anyOf: [{ $ref: "#/$defs/Nested" }, { type: "null" }], default: null };
  assert.equal(S.effective(spec, {}, root).description, "Purpose of this field");
  assert.match(S.help(spec, {}, root), /Purpose of this field\nType: object \/ null · Default: null/);
  assert.match(S.help(schema.$defs.StepBody.properties.retries, 0, schema), /additional attempts[\s\S]*Default: 0 · Minimum: 0/);
  assert.match(S.help(schema.$defs.ParamSpec.properties.env, null, schema), /parameter/);
});

test("creation fills required descendants even when a schema default is incomplete", () => {
  const spec = { type: "object", default: { child: {} }, required: ["child", "items"], properties: {
    child: { $ref: "#/$defs/Child" },
    items: { type: "array", minItems: 2, default: [], items: { $ref: "#/$defs/Child" } },
  }, $defs: { Child: { type: "object", required: ["name", "enabled"], properties: {
    name: { type: "string" }, enabled: { type: "boolean", const: true }, optional: { type: "string", default: "unused" },
  } } } };
  const result = S.initial(spec, spec);
  assert.deepEqual(result, { child: { name: "", enabled: true }, items: [{ name: "", enabled: true }, { name: "", enabled: true }] });
  result.items[0].name = "changed";
  assert.equal(result.items[1].name, "");
  assert.deepEqual(spec.default, { child: {} });
});

test("required dictionaries create their minimum entries and nested fields", () => {
  const spec = { type: "object", minProperties: 2, "x-ptk-entry-name": "route", additionalProperties: {
    anyOf: [{ type: "object", required: ["path"], properties: { path: { type: "string" } } }, { type: "null" }],
  } };
  assert.deepEqual(S.initial(spec, spec), { route: { path: "" }, route_2: { path: "" } });
});

test("runtime Artifactory and versioning templates have their required descendants", () => {
  assert.deepEqual(S.initial(schema.$defs.ArtifactoryStructure, schema), {
    url: "https://artifactory.example.invalid/artifactory", repository: "artifacts", events: { push: { path: "" } },
  });
  assert.deepEqual(S.initial(schema.$defs.VersioningSpec, schema), { project: { source: "literal", version: "0.1.0" } });
  assert.deepEqual(S.initial(schema.$defs.PythonSpec, schema), { interpreter: "cli" });
});

test("new named steps avoid collisions with all existing names", () => {
  const existing = [{ step: {} }, { step_2: {} }, { step_4: {} }];
  assert.deepEqual(S.initial(schema.$defs.StepEntry, schema, { existing }), { step_3: { run: "echo Hello" } });
  const list = { type: "array", minItems: 2, items: { $ref: "#/$defs/StepEntry" } };
  assert.deepEqual(S.initial(list, schema).map(item => Object.keys(item)[0]), ["step", "step_2"]);
});

test("new workflows reference an existing job and do not invent an unavailable one", () => {
  assert.deepEqual(S.initial(schema.$defs.WorkflowSpec, schema, { configuration: { jobs: { build: {} } } }), {
    jobs: { job: { job: "build" } },
  });
  assert.deepEqual(S.initial(schema.$defs.WorkflowSpec, schema, { configuration: { jobs: {} } }), { jobs: { job: { job: "" } } });
  assert.deepEqual(S.initial({ ...schema.$defs.WorkflowJob, "x-ptk-initial": { job: "my_repo:build" } }, schema, { configuration: { jobs: {} } }), { job: "my_repo:build" });
});

test("impossible required recursion fails clearly instead of inserting invalid null", () => {
  const spec = { $defs: { Node: { type: "object", required: ["child"], properties: { child: { $ref: "#/$defs/Node" } } } } };
  assert.throws(() => S.initial({ $ref: "#/$defs/Node" }, spec), /recursive value/);
});
