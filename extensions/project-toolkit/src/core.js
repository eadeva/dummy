"use strict";

const { execFile } = require("node:child_process");
const path = require("node:path");

const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const absolute = value => typeof value === "string" && path.isAbsolute(value);
const named = value => object(value) && typeof value.name === "string" && value.name.length > 0;

function parseInventory(text) {
  let doc;
  try { doc = JSON.parse(text); } catch {
    throw new Error("PTK did not return JSON. Update PTK to a version supporting 'describe --json'.");
  }
  if (!object(doc) || doc.schema_version !== 1 || !Array.isArray(doc.projects) ||
      !Array.isArray(doc.workflows) || !doc.workflows.every(named) || !absolute(doc.root) || typeof doc.ci !== "boolean") {
    throw new Error("Unsupported PTK inventory. Update PTK and Project Toolkit together.");
  }
  for (const project of doc.projects) {
    if (!object(project) || typeof project.alias !== "string" || !absolute(project.root) || !absolute(project.entry_file)) {
      throw new Error("Invalid repository paths in PTK inventory.");
    }
    if (project.error) continue;
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

function argsFor(target, { variant, preview = false, params = {} } = {}) {
  if (typeof preview !== "boolean" || !object(params) || !Object.values(params).every(v => typeof v === "string")) {
    throw new Error("Task preview must be a boolean and parameters must be string values.");
  }
  if (target.kind === "job" && Object.keys(params).some(key => !target.spec.params.some(p => p.name === key))) {
    throw new Error("Task contains an unknown or secret parameter. Use PTK's credential environment or terminal prompt for secrets.");
  }
  const args = target.project ? ["--config", target.project.entry_file] : [];
  if (variant && target.kind !== "workflow") args.push("--variant", variant);
  switch (target.kind) {
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
      targets.push({ kind: "workflow", name: spec.name, spec, folder, root: inventory.root, ci: inventory.ci });
    }
  }
  return targets;
}

module.exports = { parseInventory, readInventory, selectedVariant, argsFor, availableTargets };
