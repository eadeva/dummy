"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const YAML = require("yaml");
const model = require("../src/config-model");
const S = require("../media/schema");
const schema = require("../media/config-schema.json");
const { validateParameters } = require("../src/parameters");

const fixture = `# Project comment
include: [jobs/*.ptk.yml] # keep includes
vars: &shared
  greeting: 'hello' # greeting comment
copy: *shared
jobs:
  build:
    steps: !append
      # step comment
      - hello: {run: echo hello}
external: !include other.ptk.yml
replace: !replace {old: true}
`;

test("field edits preserve comments, anchors, aliases, include paths and merge tags", () => {
  const result = model.edit(fixture, [{ op: "set", path: ["vars", "greeting"], value: "world" },
    { op: "add", path: ["jobs", "build", "open_report"], value: "on_errors" }]);
  for (const expected of ["# Project comment", "# keep includes", "# greeting comment", "# step comment", "&shared", "*shared", "!append", "!include other.ptk.yml", "!replace", "jobs/*.ptk.yml"]) assert.ok(result.includes(expected), expected);
  const doc = YAML.parseDocument(result);
  assert.equal(doc.getIn(["vars", "greeting"]), "world");
  assert.equal(doc.getIn(["jobs", "build", "open_report"]), "on_errors");
  assert.throws(() => model.edit(result, [{ op: "set", path: ["copy", "greeting"], value: "bad" }]), /alias/);
  assert.throws(() => model.edit(result, [{ op: "set", path: ["external"], value: "bad" }]), /include/);
});

test("new jobs use model fields and produce authored named steps", () => {
  const value = S.initial(schema.$defs.JobSpec, schema);
  const text = model.edit("jobs: {}\n", [{ op: "add", path: ["jobs", "test"], value }]);
  assert.deepEqual(YAML.parse(text), { jobs: { test: { steps: [{ step: { run: "echo Hello" } }] } } });
  assert.equal(S.at(schema, YAML.parse(text), ["jobs", "test", "open_report"], schema).default, null);
  const nullable = schema.$defs.ParamSpec.properties.choices;
  assert.deepEqual(S.initial(nullable, schema), []);
  assert.equal(S.effective(nullable, [], schema).type, "array");
});

test("every bundled model field is reachable and defaults retain their JSON types", () => {
  for (const definition of [schema, ...Object.values(schema.$defs)]) {
    for (const [key, field] of Object.entries(definition.properties || {})) {
      const child = S.child(definition, {}, key, schema);
      assert.deepEqual(child, field, `${definition.title}.${key}`);
      if (Object.hasOwn(field, "default") && field.default !== null) {
        assert.deepEqual(S.initial(child, schema), field.default, `${definition.title}.${key}`);
      }
    }
  }
  assert.deepEqual(S.initial(schema.$defs.ReportingSpec.properties.formats, schema), ["json", "html"]);
  assert.deepEqual(S.initial(schema.$defs.CredentialSpec.properties.providers, schema), ["env", "keyring", "gopass", "vault", "prompt"]);
  assert.deepEqual(S.initial(schema.$defs.ToolbaseSource.properties.bin, schema), ["."]);
  // Defaults on a selected union branch and literal-only fields also apply.
  assert.equal(S.initial({ anyOf: [{ type: "integer", default: 9 }, { type: "null" }] }, schema), 9);
  assert.equal(S.initial({ type: "integer", const: 1 }, schema), 1);
  const formats = S.initial(schema.$defs.ReportingSpec.properties.formats, schema);
  formats.push("changed");
  assert.deepEqual(schema.$defs.ReportingSpec.properties.formats.default, ["json", "html"]);
  assert.deepEqual(S.initial(schema, schema), {}); // No eager optional fields.
});

test("edits reject stale paths, duplicate keys, multiple documents and unsafe payloads", () => {
  assert.throws(() => model.inspect("x: 1\nx: 2\n"), /unique/);
  assert.throws(() => model.inspect("---\nx: 1\n---\ny: 2\n"), /multiple documents/);
  assert.throws(() => model.edit("x: 1\n", [{ op: "add", path: ["x"], value: 2 }]), /already exists/);
  assert.throws(() => model.edit("x: 1\n", [{ op: "set", path: ["y"], value: 2 }]), /no longer exists/);
  assert.throws(() => model.edit("x: 1\n", [{ op: "set", path: ["__proto__", "polluted"], value: true }]), /Invalid/);
  assert.throws(() => model.edit("x: 1\n", [{ op: "set", path: ["x"], value: JSON.parse('{"__proto__":{"bad":true}}') }]), /Unsupported/);
  assert.throws(() => model.edit("x: 1\n", [{ op: "set", path: ["x"], value: Infinity }]), /Invalid/);
  assert.equal({}.polluted, undefined);
});

test("list insertion, movement and deletion preserve step comments; edits preserve CRLF and BOM", () => {
  const before = '\uFEFFsteps:\r\n    # first\r\n    - a: echo a\r\n    - b: echo b\r\n';
  const after = model.edit(before, [
    { op: "add", path: ["steps", 2], value: { c: "echo c" } },
    { op: "move", path: ["steps", 0], direction: 1 },
    { op: "remove", path: ["steps", 2] },
  ]);
  assert.ok(after.startsWith("\uFEFF"));
  assert.ok(after.includes("# first"));
  assert.equal(after.replaceAll("\r\n", "").includes("\n"), false);
  assert.deepEqual(YAML.parse(after).steps, [{ b: "echo b" }, { a: "echo a" }]);
  const patch = model.minimalEdit(before, after);
  assert.equal(before.slice(0, patch.start) + patch.text + before.slice(patch.end), after);
});

test("empty YAML and fragments can be edited without synthesizing a project", () => {
  assert.deepEqual(YAML.parse(model.edit("# empty\n", [{ op: "add", path: ["jobs"], value: {} }])), { jobs: {} });
  assert.equal(S.infer({ default: "debug", variants: {} }), "ProductLineSpec");
  assert.equal(S.infer([{ test: "echo test" }]), "steps");
  assert.equal(S.infer({ jobs: {} }), "configuration");
  const text = model.edit("- first: echo hi\n", [{ op: "add", path: [1], value: { second: "echo there" } }]);
  assert.equal(YAML.parse(text).length, 2);
});

test("parameter types, required values, environment fallback and secret exclusions are enforced", () => {
  const specs = [{ name: "count", type: "int", required: true }, { name: "verbose", type: "bool" },
    { name: "ratio", type: "float" }, { name: "mode", type: "choice", choices: ["debug", "release"] },
    { name: "path", type: "path" }, { name: "from_env", type: "str", required: true, env: "INPUT" }, { name: "secret", type: "secret" }];
  const values = { count: "3", verbose: "false", ratio: "1.5", mode: "debug", path: "spaces; $(literal)" };
  assert.equal(validateParameters(specs, values), values);
  for (const invalid of [{ count: "1.5" }, { count: "1", verbose: "yes" }, { count: "1", ratio: "NaN" }, { count: "1", mode: "other" }, { count: "1", secret: "no" }, {}]) assert.throws(() => validateParameters(specs, invalid));
  assert.deepEqual(validateParameters([{ name: "optional", type: "int", default: 42 }], {}), {});
});

test("YAML scalar semantics match PTK and large integers and timestamps stay intact", () => {
  const text = "enabled: yes\ny: single-letter key\nlarge: 9007199254740993\ncreated: 2024-01-01\nproject: {name: old}\n";
  const state = model.inspect(text);
  assert.equal(state.value.enabled, true);
  assert.deepEqual({ ...model.inspect("a: false\nb: no\nc: off\nd: true\nn: letter\n").value }, { a: false, b: false, c: false, d: true, n: "letter" });
  assert.equal(state.value.y, "single-letter key");
  assert.equal(state.value.large, "9007199254740993");
  const result = model.edit(text, [{ op: "set", path: ["project", "name"], value: "on" }]);
  assert.match(result, /name: ["']on["']/);
  assert.match(result, /large: 9007199254740993/);
  assert.match(result, /created: 2024-01-01/);
  assert.throws(() => model.edit(text, [{ op: "set", path: ["large"], value: 1 }]), /complex YAML/);
});

test("renaming a job preserves its comments and does not replace an existing job", () => {
  const text = "jobs:\n  # job comment\n  old: {steps: []}\n  other: {steps: []}\n";
  const result = model.edit(text, [{ op: "rename", path: ["jobs", "old"], name: "build" }]);
  assert.ok(result.includes("# job comment"));
  assert.deepEqual(Object.keys(YAML.parse(result).jobs), ["build", "other"]);
  assert.throws(() => model.edit(text, [{ op: "rename", path: ["jobs", "old"], name: "other" }]), /already exists/);
});
