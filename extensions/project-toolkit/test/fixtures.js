"use strict";

const path = require("node:path");

function inventory(root = path.resolve("test project")) {
  return {
    schema_version: 1, mode: "repository", root, ci: false, workflows: [],
    projects: [{
      alias: "demo", name: "Demo", root, entry_file: path.join(root, ".main.ptk.yml"),
      config_files: [path.join(root, ".main.ptk.yml")],
      capabilities: { variants: true, validate: true, reports: true },
      default_variant: "small",
      variants: [{ name: "base", abstract: true }, { name: "small" }, { name: "large" }],
      jobs: [{ name: "build", help: "Build firmware", params: [
        { name: "output_path", type: "path", choices: [], required: false },
        { name: "verbose", type: "bool", choices: [], required: false },
      ] }],
      workflows: [{ name: "build", help: "Verify all repositories" }],
    }],
  };
}

module.exports = { inventory };
