"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const { canonicalPath } = require("../src/file-path");
const { schemaForFile, bindingsForFile } = require("../src/project-edits");

test("raw schemas and variables match directory aliases and new entity paths", t => {
  const container = fs.mkdtempSync(path.join(os.tmpdir(), "ptk file identity "));
  t.after(() => fs.rmSync(container, { recursive: true, force: true }));
  const root = path.join(container, "physical"), alias = path.join(container, "alias");
  fs.mkdirSync(path.join(root, "jobs"), { recursive: true });
  fs.symlinkSync(root, alias, process.platform === "win32" ? "junction" : "dir");
  const template = path.join(fs.realpathSync.native(root), "jobs/{name}.ptk.yml");
  const config = { schema: { $defs: {} },
    documents: [{ file: template, schema: { title: "Job" } }],
    bindings: [{ file: template, path: ["jobs", "*"], document_path: [] }],
  };
  for (const name of ["existing", "new-job"]) {
    if (name === "existing") fs.writeFileSync(path.join(root, `jobs/${name}.ptk.yml`), "{}");
    const file = path.join(alias, `jobs/${name}.ptk.yml`);
    assert.equal(schemaForFile(config, file).title, "Job");
    assert.deepEqual(bindingsForFile(config, file)[0].path, ["jobs", name]);
    assert.equal(canonicalPath(file), path.join(fs.realpathSync.native(root), `jobs/${name}.ptk.yml`));
  }
  assert.equal(schemaForFile(config, path.join(container, "outside.ptk.yml")), undefined);
  assert.deepEqual(bindingsForFile(config, path.join(alias, "jobs/nested/build.ptk.yml")), []);
});
