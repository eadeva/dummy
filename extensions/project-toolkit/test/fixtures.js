"use strict";

const path = require("node:path");

function builtinParam(name, overrides = {}) {
  return { name, kind: "argument", required: false, type: "text", choices: [], nargs: 1,
    multiple: false, is_flag: false, option: null, secondary_option: null, ...overrides };
}

function builtinCommands() {
  const command = (path, params = [], children = [], runnable = !children.length) => ({
    name: path.at(-1), path, params, children, runnable, help: `Help for ${path.join(" ")}`,
  });
  return [
    command(["help"]),
    command(["setup"], [], [
      command(["setup", "creds"], [], [
        command(["setup", "creds", "list"], [builtinParam("name")]),
        command(["setup", "creds", "set"], [builtinParam("name", { required: true }), builtinParam("field")]),
      ]),
      command(["setup", "config"], [], [
        command(["setup", "config", "show"], [
          builtinParam("path"), builtinParam("fmt", { kind: "option", option: "--format", type: "choice", choices: ["json", "yaml"] }),
        ]),
      ]),
    ], true),
  ];
}

function inventory(root = path.resolve("test project")) {
  return {
    schema_version: 1, mode: "repository", root, ci: false, workflows: [],
    projects: [{
      alias: "demo", name: "Demo", root, entry_file: path.join(root, ".main.ptk.yml"),
      config_files: [path.join(root, ".main.ptk.yml")],
      capabilities: { variants: true, validate: true, reports: true },
      default_variant: "small",
      commands: builtinCommands(),
      variants: [{ name: "base", abstract: true }, { name: "small" }, { name: "large" }],
      jobs: [{ name: "build", help: "Build firmware", params: [
        { name: "output_path", type: "path", choices: [], required: false },
        { name: "verbose", type: "bool", choices: [], required: false },
      ] }],
      workflows: [{ name: "build", help: "Verify all repositories" }],
    }],
  };
}

module.exports = { inventory, builtinParam, builtinCommands };
