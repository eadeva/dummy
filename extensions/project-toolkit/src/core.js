"use strict";

const { execFile } = require("node:child_process");
const path = require("node:path");

const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const absolute = value => typeof value === "string" && path.isAbsolute(value);
const named = value => object(value) && typeof value.name === "string" && value.name.length > 0;

function validBuiltinParam(param) {
  return named(param) && ["option", "argument"].includes(param.kind) && typeof param.required === "boolean" &&
    Number.isInteger(param.nargs) && (param.nargs === -1 || param.nargs > 0) &&
    typeof param.multiple === "boolean" && typeof param.is_flag === "boolean" &&
    Array.isArray(param.choices) && param.choices.every(choice => typeof choice === "string") &&
    (param.kind === "argument" || typeof param.option === "string" && param.option.startsWith("-")) &&
    (param.secondary_option == null || typeof param.secondary_option === "string" && param.secondary_option.startsWith("-"));
}

function validCommands(commands) {
  return commands === undefined || Array.isArray(commands) && commands.every(command => named(command) &&
    Array.isArray(command.path) && command.path.length && command.path.every(word => typeof word === "string" && word.length && !word.startsWith("-")) &&
    typeof command.runnable === "boolean" && Array.isArray(command.children) && validCommands(command.children) &&
    Array.isArray(command.params) && command.params.every(validBuiltinParam));
}

function parseInventory(text) {
  let doc;
  try { doc = JSON.parse(text); } catch {
    throw new Error("PTK did not return JSON. Update PTK to a version supporting 'describe --json'.");
  }
  if (!object(doc) || doc.schema_version !== 1 || !Array.isArray(doc.projects) ||
      !Array.isArray(doc.workflows) || !doc.workflows.every(named) || !absolute(doc.root) || typeof doc.ci !== "boolean") {
    throw new Error("Unsupported PTK inventory. Update PTK and Project Toolkit together.");
  }
  if (!validCommands(doc.commands)) throw new Error("Invalid PTK built-in command inventory.");
  for (const project of doc.projects) {
    if (!object(project) || typeof project.alias !== "string" || !absolute(project.root) || !absolute(project.entry_file)) {
      throw new Error("Invalid repository paths in PTK inventory.");
    }
    if (project.error) continue;
    if (!validCommands(project.commands)) throw new Error("Invalid PTK built-in command inventory.");
    if (![project.jobs, project.workflows, project.variants].every(items => Array.isArray(items) && items.every(named)) ||
        !object(project.capabilities) || !["validate", "variants", "reports"].every(key => typeof project.capabilities[key] === "boolean") ||
        !Array.isArray(project.config_files) || !project.config_files.every(absolute) ||
        !project.jobs.every(job => Array.isArray(job.params) && job.params.every(param => named(param) &&
          ["str", "int", "float", "bool", "path", "choice", "list"].includes(param.type) &&
          typeof param.required === "boolean" && Array.isArray(param.choices) && param.choices.every(c => typeof c === "string")))) {
      throw new Error("Incomplete PTK project inventory.");
    }
  }
  return doc;
}

function readInventory(settings, cwd) {
  return new Promise((resolve, reject) => {
    execFile(settings.executable, [...settings.arguments, "describe", "--json"], {
      cwd, timeout: settings.timeout * 1000, maxBuffer: 8 * 1024 * 1024,
      windowsHide: true, encoding: "utf8", shell: false,
    }, (error, stdout, stderr) => {
      if (error) {
        const reason = error.killed ? "Discovery timed out." : error.code === "ENOENT"
          ? "PTK executable not found. Install PTK or configure projectToolkit.executable."
          : (stderr.trim() || stdout.trim() || error.message).slice(-4000);
        reject(new Error(reason));
        return;
      }
      try { resolve(parseInventory(stdout)); } catch (cause) { reject(cause); }
    });
  });
}

function selectedVariant(project, saved) {
  const concrete = project.variants.filter(v => !v.abstract);
  if (concrete.some(v => v.name === saved)) return saved;
  return concrete.some(v => v.name === project.default_variant) ? project.default_variant : undefined;
}

function builtinArgs(spec, inputs = {}) {
  if (!object(inputs) || Object.entries(inputs).some(([key, values]) =>
    !spec.params.some(p => p.name === key) || !Array.isArray(values) || !values.every(value => typeof value === "string"))) {
    throw new Error("Invalid built-in command arguments.");
  }
  const options = [], positional = [];
  let omittedArgument = false;
  for (const param of spec.params) {
    const values = Object.hasOwn(inputs, param.name) ? inputs[param.name] : [];
    if (!values.length) {
      if (param.required) throw new Error(`Required argument: ${param.name}`);
      if (param.kind === "argument") omittedArgument = true;
      continue;
    }
    if (param.kind === "argument" && omittedArgument) throw new Error(`Supply preceding positional arguments before ${param.name}.`);
    if (param.is_flag) {
      if (values.length !== 1 || !["true", "false"].includes(values[0])) throw new Error(`Invalid flag: ${param.name}`);
      if (values[0] === "true") options.push(param.option);
      else if (param.secondary_option) options.push(param.secondary_option);
    } else if (param.kind === "argument") {
      if (param.nargs !== -1 && values.length !== param.nargs) throw new Error(`Invalid number of values for ${param.name}.`);
      positional.push(...values);
    } else {
      if ((!param.multiple && values.length !== param.nargs) || values.length % param.nargs) throw new Error(`Invalid number of values for ${param.name}.`);
      for (let i = 0; i < values.length; i += param.nargs) {
        // Bind a leading-dash value to its option rather than parsing it as a flag.
        options.push(`${param.option}=${values[i]}`, ...values.slice(i + 1, i + param.nargs));
      }
    }
  }
  return [...options, ...(positional.length ? ["--", ...positional] : [])];
}

function argsFor(target, { variant, preview = false, params = {}, help = false, inputs = {}, clean = false, reRun = false, report = false } = {}) {
  if (typeof clean !== "boolean" || typeof reRun !== "boolean" || clean && reRun) throw new Error("Choose clean or re-run.");
  if ((clean || reRun) && !["job", "workflow"].includes(target.kind)) throw new Error("Cleanup applies to jobs and workflows.");
  if (typeof help !== "boolean") throw new Error("Task help must be a boolean.");
  if (typeof preview !== "boolean" || !object(params) || !Object.values(params).every(v => typeof v === "string")) {
    throw new Error("Dry-run mode must be a boolean and parameters must be string values.");
  }
  if (target.kind === "job" && Object.keys(params).some(key => !target.spec.params.some(p => p.name === key))) {
    throw new Error("Task contains an unknown or secret parameter. Use PTK's credential environment or terminal prompt for secrets.");
  }
  const args = target.project ? ["--config", target.project.entry_file] : [];
  if (typeof report !== "boolean") throw new Error("Report mode must be a boolean.");
  if (report) {
    if (preview || help || clean || reRun) throw new Error("Open a report separately from run, help or cleanup actions.");
    if (target.kind === "workflow") return [...args, "workflow", "report", "--if-exists", "--", target.name];
    if (target.kind !== "job") throw new Error("Reports apply to jobs and workflows.");
    if (variant) args.push("--variant", variant);
    return [...args, "report", "open", "--if-exists", "--", target.name];
  }
  if (variant && target.kind !== "builtin") args.push("--variant", variant);
  if (!help && clean) args.push("--clean");
  if (!help && reRun) args.push("--re-run");
  if (help) {
    if (target.kind === "job") return [...args, target.name, "--help"];
    if (target.kind === "workflow") return [...args, "workflow", "run", target.name, "--help"];
    if (target.kind === "builtin") return [...args, ...target.spec.path, "--help"];
  }
  switch (target.kind) {
    case "builtin":
      if (preview) throw new Error("Built-in commands do not support generic dry runs. Use their --dry-run option where available.");
      if (!target.spec.runnable) throw new Error("Choose a subcommand or open this command's help.");
      args.push(...target.spec.path, ...builtinArgs(target.spec, inputs));
      break;
    case "job":
      args.push(...(preview ? ["dry-run", target.name] : ["run", target.name]));
      for (const [key, value] of Object.entries(params)) {
        // Generic run accepts --param. A dry-run job has generated typed options.
        if (!preview) args.push("--param", `${key}=${value}`);
        else {
          const spec = target.spec.params.find(p => p.name === key);
          const option = key.replaceAll("_", "-");
          if (spec?.type === "bool") {
            if (!["true", "false"].includes(value)) throw new Error(`Boolean parameter ${key} must be true or false.`);
            args.push(value === "true" ? `--${option}` : `--no-${option}`);
          }
          else args.push(`--${option}`, String(value));
        }
      }
      break;
    case "workflow": args.push("workflow", preview ? "dry-run" : "run", target.name); break;
    case "variant": args.push("variant", "show", target.name); break;
    case "report": args.push("report", "open", target.name); break;
    case "validate": args.push("setup", "config", "validate"); break;
    default: throw new Error(`Unsupported PTK operation: ${target.kind}`);
  }
  return args;
}

function availableTargets(records) {
  const targets = [];
  for (const record of records) {
    if (!record.inventory) continue;
    const { inventory, folder } = record;
    for (const project of inventory.projects) {
      if (project.error) continue;
      for (const kind of ["job", "workflow"]) {
        for (const spec of project[`${kind}s`]) {
          targets.push({ kind, name: spec.name, spec, project, folder, root: project.root, ci: inventory.ci });
        }
      }
    }
    for (const spec of inventory.workflows) {
      targets.push({ kind: "workflow", name: spec.name, spec, folder, root: inventory.root, ci: inventory.ci, commands: inventory.commands });
    }
  }
  return targets;
}

function builtinTargets(owner, commands = []) {
  const result = [{ ...owner, kind: "builtin", name: "--help", spec: { name: "CLI help", path: [], params: [], children: [], runnable: false } }];
  function visit(items) {
    for (const spec of items) {
      result.push({ ...owner, kind: "builtin", name: spec.path.join(" "), spec });
      visit(spec.children);
    }
  }
  visit(commands);
  return result;
}

function availableBuiltins(records) {
  return records.flatMap(({ inventory, folder }) => {
    if (!inventory) return [];
    const common = { folder, ci: inventory.ci };
    return [
      ...inventory.projects.filter(project => !project.error).flatMap(project =>
        builtinTargets({ ...common, project, root: project.root }, project.commands)),
      ...(inventory.mode === "workspace" ? builtinTargets({ ...common, root: inventory.root }, inventory.commands) : []),
    ];
  });
}

function canOpenReport(target) {
  if (target.kind === "job" && !target.project?.capabilities.reports) return false;
  const commands = target.project?.commands ?? target.commands;
  if (!commands) return target.kind === "job";
  const name = target.kind === "job" ? "report open" : "workflow report";
  return builtinTargets({}, commands).some(command => command.name === name && command.spec.runnable);
}

module.exports = { parseInventory, readInventory, selectedVariant, argsFor, availableTargets, availableBuiltins, builtinTargets, canOpenReport };
