"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const S = require("../media/schema");
const schema = require("../media/config-schema.json");

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
    steps: [{ job: { job: "build" } }],
  });
  assert.throws(() => S.initial(schema.$defs.WorkflowSpec, schema, { configuration: { jobs: {} } }), /Create a job/);
});

test("impossible required recursion fails clearly instead of inserting invalid null", () => {
  const spec = { $defs: { Node: { type: "object", required: ["child"], properties: { child: { $ref: "#/$defs/Node" } } } } };
  assert.throws(() => S.initial({ $ref: "#/$defs/Node" }, spec), /recursive value/);
});
