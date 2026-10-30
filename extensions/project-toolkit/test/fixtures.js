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
    command(["validate"], [builtinParam("variants", { kind: "option", option: "--variants", type: "boolean", is_flag: true })]),
    command(["report"], [], [command(["report", "open"]), command(["report", "export"])]),
    command(["workflow"], [], ["list", "show", "run"].map(name => command(["workflow", name]))),
    command(["self-service"], [], [
      command(["self-service", "creds"], [], [
        command(["self-service", "creds", "list"], [builtinParam("name")]),
        command(["self-service", "creds", "set"], [builtinParam("name", { required: true }), builtinParam("field")]),
      ]),
    ], true),
    command(["maintainer"], [], [
      command(["maintainer", "config"], [], [
        command(["maintainer", "config", "show"], [
          builtinParam("path"), builtinParam("fmt", { kind: "option", option: "--format", type: "choice", choices: ["json", "yaml"] }),
        ]),
      ]),
    ], true),
  ];
}

function inventory(root = path.resolve("test project")) {
  return {
    schema_version: 4, mode: "repository", root, ci: false, workflows: [], commands: [],
    projects: [{
      alias: "demo", name: "Demo", root, entry_file: path.join(root, ".main.ptk.yml"),
      invocation: { cwd: root, prefix: [] },
      config_files: [path.join(root, ".main.ptk.yml")],
      configuration: { version: 5, graphs: [], bindings: [], documents: [], schema: { properties: { project: {}, jobs: {}, variants: {} } }, value: { jobs: { build: { help: "Build" } } }, sources: [], files: [path.join(root, ".main.ptk.yml")] },
      capabilities: { variants: true, validate: true, reports: true },
      default_variant: "small",
      commands: builtinCommands(),
      variants: [{ name: "base", abstract: true }, { name: "small" }, { name: "large" }],
      jobs: [{ name: "build", command: ["run", "build"], help_command: ["build"], help: "Build firmware", run_options: [], params: [
        { name: "output_path", type: "path", choices: [], required: false },
        { name: "verbose", type: "bool", choices: [], required: false },
      ] }],
      workflows: [{ name: "build", command: ["workflow", "run", "build"], help: "Verify all repositories", run_options: [] }],
    }],
  };
}

module.exports = { inventory, builtinParam, builtinCommands };
