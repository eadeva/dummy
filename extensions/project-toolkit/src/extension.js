"use strict";

const path = require("node:path");
const core = require("./core");

// VS Code is injected so command dispatch and trust boundaries can be tested
// without pretending a mock is a graphical extension-host acceptance test.
function createController(vscode, context) {
  let records = [];
  let revision = 0;
  let timer;
  let disposed = false;
  let pending = Promise.resolve();
  const changed = new vscode.EventEmitter();
  const output = vscode.window.createOutputChannel("Project Toolkit");
  context.subscriptions.push(changed, output);

  function trusted() {
    if (!vscode.workspace.isTrusted) throw new Error("Trust this workspace before running PTK.");
  }

  function settings(folder) {
    const config = vscode.workspace.getConfiguration("projectToolkit", folder.uri);
    const value = {
      executable: config.get("executable", "ptk"),
      arguments: config.get("arguments", []),
      timeout: config.get("discoveryTimeout", 30),
    };
    if (typeof value.executable !== "string" || !value.executable.trim() ||
        !Array.isArray(value.arguments) || !value.arguments.every(a => typeof a === "string") ||
        !Number.isFinite(value.timeout) || value.timeout < 1 || value.timeout > 300) {
      throw new Error("Invalid Project Toolkit executable, arguments or discoveryTimeout settings.");
    }
    return value;
  }

  function refresh() {
    const current = ++revision;
    clearTimeout(timer);
    if (!vscode.workspace.isTrusted || disposed) {
      records = [];
      changed.fire();
      return Promise.resolve();
    }
    const folders = (vscode.workspace.workspaceFolders || []).filter(folder => folder.uri.scheme === "file");
    pending = Promise.all(folders.map(async folder => {
      try {
        return { folder, inventory: await core.readInventory(settings(folder), folder.uri.fsPath) };
      } catch (error) {
        return { folder, error: error.message };
      }
    })).then(result => {
      if (current !== revision || disposed) return;
      records = result;
      for (const record of records) {
        if (record.error) output.appendLine(`${record.folder.name}: ${record.error}`);
      }
      changed.fire();
    });
    return pending;
  }

  function schedule(uri) {
    if (uri && path.basename(uri.fsPath) === ".gen.version.ptk.yml") return;
    clearTimeout(timer);
    timer = setTimeout(refresh, 350);
  }

  const variantKey = project => `variant:${project.entry_file}`;
  const variantFor = project => core.selectedVariant(project, context.workspaceState.get(variantKey(project)));
  const title = target => `${target.project?.alias || path.basename(target.root)} / ${target.kind} / ${target.name}`;

  function builtinTree(owner, commands) {
    const targets = core.builtinTargets(owner, commands);
    const nodes = new Map(targets.map(target => [target.name, {
      ...target, label: target.spec.name, tooltip: target.spec.help,
      id: JSON.stringify([owner.folder.uri.fsPath, owner.project?.entry_file || owner.root, "builtin", target.name]),
      icon: target.spec.children.length ? "folder" : "terminal",
      collapsed: true, contextValue: target.spec.runnable ? "builtin" : "builtin-group",
    }]));
    for (const node of nodes.values()) {
      if (node.spec.children.length) node.children = node.spec.children.map(child => nodes.get(child.path.join(" ")));
    }
    const help = nodes.get("--help");
    help.icon = "question";
    help.command = { command: "project-toolkit.showHelp", title: "Show CLI help", arguments: [targets[0]] };
    const children = [help, ...(commands || []).map(spec => nodes.get(spec.path.join(" ")))];
    if (!commands) children.push({ label: "Update PTK to browse built-in commands", icon: "info" });
    return { label: "Built-in commands", children, icon: "terminal" };
  }

  function projectNode(project, record) {
    const common = { project, folder: record.folder, root: project.root, ci: record.inventory.ci };
    if (project.error) return { ...common, label: project.alias, description: "configuration error", tooltip: project.error, icon: "error" };
    const variants = project.variants.filter(v => !v.abstract);
    const groups = [];
    for (const kind of ["job", "workflow"]) {
      const children = project[`${kind}s`].map(spec => ({
        ...common, kind, name: spec.name, spec, label: spec.name, tooltip: spec.help,
        contextValue: kind === "job" && project.capabilities.reports ? "job-report" : kind,
        description: kind === "workflow" ? (common.ci ? "dry-run only on CI" : "local") : (spec.default ? "default" : ""),
        icon: kind === "job" ? "tools" : "git-merge",
      }));
      if (children.length) groups.push({ label: kind === "job" ? "Jobs" : "Workflows", children });
    }
    if (variants.length) groups.push({ label: "Variants", children: variants.map(spec => ({
      ...common, kind: "variant", name: spec.name, label: spec.name, tooltip: spec.description,
      description: variantFor(project) === spec.name ? "selected" : "", contextValue: "variant", icon: "symbol-enum",
      command: { command: "project-toolkit.selectVariant", title: "Select variant", arguments: [{ ...common, name: spec.name }] },
    })) });
    if (project.capabilities.validate) groups.push({
      ...common, label: "Validate configuration", icon: "check",
      command: { command: "project-toolkit.validate", title: "Validate", arguments: [common] },
    });
    groups.push(builtinTree(common, project.commands));
    groups.push({ label: "Configuration", children: project.config_files.map(file => ({
      label: path.relative(project.root, file), icon: "file-code", tooltip: file,
      command: { command: "vscode.open", title: "Open configuration", arguments: [vscode.Uri.file(file)] },
    })) });
    return { ...common, label: project.alias, description: variantFor(project) || project.name, tooltip: project.root,
      contextValue: variants.length ? "project-variants" : "project", icon: "repo", children: groups };
  }

  const provider = {
    onDidChangeTreeData: changed.event,
    getChildren(element) {
      if (element) return element.children || [];
      return records.map(record => {
        if (record.error) return { label: record.folder.name, description: "PTK unavailable", tooltip: record.error, icon: "warning" };
        const children = record.inventory.projects.map(project => projectNode(project, record));
        if (record.inventory.workflows.length) children.unshift({ label: "Workspace workflows", children: record.inventory.workflows.map(spec => ({
          kind: "workflow", name: spec.name, spec, root: record.inventory.root, folder: record.folder, ci: record.inventory.ci,
          label: spec.name, tooltip: spec.help, icon: "git-merge", contextValue: "workflow",
        })) });
        if (record.inventory.mode === "workspace") children.push(builtinTree({ root: record.inventory.root, folder: record.folder, ci: record.inventory.ci }, record.inventory.commands));
        return { label: record.folder.name, description: record.inventory.mode === "workspace" ? "VMR" : "", children, icon: "root-folder" };
      });
    },
    getTreeItem(element) {
      const item = new vscode.TreeItem(element.label, element.children
        ? element.collapsed ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None);
      item.id = element.id;
      item.description = element.description;
      item.tooltip = element.tooltip;
      item.contextValue = element.contextValue;
      item.command = element.command;
      if (element.icon) item.iconPath = new vscode.ThemeIcon(element.icon);
      return item;
    },
  };
  context.subscriptions.push(vscode.window.registerTreeDataProvider("project-toolkit.projects", provider));

  async function chooseProject(element, capability) {
    trusted();
    await pending;
    const candidates = records.flatMap(record => (record.inventory?.projects || [])
      .filter(project => !project.error && (!capability || project.capabilities[capability]))
      .map(project => ({ project, folder: record.folder, root: project.root, ci: record.inventory.ci })));
    const existing = element?.project && candidates.find(item => item.project.entry_file === element.project.entry_file);
    if (existing) return existing;
    if (element?.project) throw new Error("This operation is no longer available. Refresh projects.");
    const selected = await vscode.window.showQuickPick(candidates.map(item => ({ label: item.project.alias, description: item.root, item })), { placeHolder: "Choose a PTK repository" });
    return selected?.item;
  }

  async function chooseTarget(element, jobsOnly = false) {
    trusted();
    await pending;
    const targets = core.availableTargets(records).filter(t => !jobsOnly || t.kind === "job");
    if (element?.kind) {
      const found = targets.find(t => t.root === element.root && t.kind === element.kind && t.name === element.name);
      if (!found) throw new Error("This job or workflow is no longer available. Refresh projects.");
      return found;
    }
    const selected = await vscode.window.showQuickPick(targets.map(target => ({ label: title(target), description: target.spec.help, target })), { placeHolder: "Choose a PTK job or workflow" });
    return selected?.target;
  }

  async function chooseBuiltin(element, helpOnly = false) {
    trusted();
    await pending;
    const targets = core.availableBuiltins(records).filter(target => helpOnly || target.spec.runnable);
    if (element?.kind) {
      const found = targets.find(target => target.root === element.root && target.name === element.name && target.project?.entry_file === element.project?.entry_file);
      if (!found) throw new Error("This command is no longer available. Refresh projects.");
      return found;
    }
    const selected = await vscode.window.showQuickPick(targets.map(target => ({ label: title(target), description: target.spec.help, target })), { placeHolder: "Choose a PTK command" });
    return selected?.target;
  }

  async function selectVariant(element) {
    const owner = await chooseProject(element, "variants");
    if (!owner) return;
    const choices = owner.project.variants.filter(v => !v.abstract);
    let selected = choices.find(v => v.name === element?.name);
    if (!selected) selected = await vscode.window.showQuickPick([
      { label: "Use project default", description: owner.project.default_variant || "No default configured", reset: true },
      ...choices.map(v => ({ label: v.name, description: v.description, name: v.name })),
    ], { placeHolder: `Variant for ${owner.project.alias} jobs (configuration stays unchanged)` });
    if (!selected) return;
    if (selected.reset) {
      await context.workspaceState.update(variantKey(owner.project), undefined);
      changed.fire();
      return variantFor(owner.project);
    }
    await context.workspaceState.update(variantKey(owner.project), selected.name);
    changed.fire();
    return selected.name;
  }

  async function parameters(target, editOptional) {
    const specs = target.spec.params || [];
    const selected = new Set(specs.filter(p => p.required).map(p => p.name));
    if (editOptional) {
      const picked = await vscode.window.showQuickPick(specs.map(p => ({ label: p.name, description: p.help, picked: p.required })), { canPickMany: true, placeHolder: "Parameters to override; required parameters are always prompted" });
      if (!picked) return;
      for (const item of picked) selected.add(item.label);
    }
    const values = {};
    for (const spec of specs.filter(p => selected.has(p.name))) {
      const choices = spec.type === "bool" ? ["true", "false"] : spec.choices;
      const value = choices.length ? await vscode.window.showQuickPick(choices, { placeHolder: spec.name })
        : await vscode.window.showInputBox({ title: `${target.name}: ${spec.name}`, prompt: spec.help || `Value (${spec.type})` });
      if (value === undefined) return;
      values[spec.name] = value;
    }
    return values;
  }

  async function builtinParameters(target, editOptional) {
    const specs = target.spec.params;
    const selected = new Set(specs.filter(param => param.required).map(param => param.name));
    if (editOptional) {
      const picked = await vscode.window.showQuickPick(specs.map(param => ({
        label: param.option || param.name.toUpperCase(), description: param.help, param, picked: param.required,
      })), { canPickMany: true, placeHolder: "Arguments and options to supply; omitted options keep PTK defaults" });
      if (!picked) return;
      for (const item of picked) selected.add(item.param.name);
    }
    // Positional arguments cannot skip an earlier optional slot.
    const arguments_ = specs.filter(param => param.kind === "argument");
    const last = arguments_.findLastIndex(param => selected.has(param.name));
    for (const param of arguments_.slice(0, last + 1)) selected.add(param.name);
    const inputs = {};
    for (const param of specs.filter(param => selected.has(param.name))) {
      const values = [];
      const repeated = param.multiple || param.nargs === -1;
      let more;
      do {
        for (let i = 0; i < Math.max(1, param.nargs); i++) {
          const choices = param.is_flag ? ["true", "false"] : param.choices;
          const prompt = `${target.name}: ${param.option || param.name}${repeated || param.nargs > 1 ? ` (${values.length + 1})` : ""}`;
          const value = choices.length ? await vscode.window.showQuickPick(choices, { placeHolder: prompt })
            : await vscode.window.showInputBox({ title: prompt, prompt: param.help || "Enter one value; spaces are preserved" });
          if (value === undefined) return;
          values.push(value);
        }
        more = repeated ? await vscode.window.showQuickPick(["Done", "Add another value"], { placeHolder: `More values for ${param.option || param.name}?` }) : "Done";
        if (more === undefined) return;
      } while (more !== "Done");
      inputs[param.name] = values;
    }
    return inputs;
  }

  function makeTask(target, options = {}) {
    trusted();
    const config = settings(target.folder);
    if (target.kind === "workflow" && target.ci && !options.preview && !options.help) throw new Error("Workflows run locally only; CI can dry-run workflows or run individual jobs.");
    const definition = { type: "project-toolkit", kind: target.kind, name: target.name, root: target.root };
    if (options.variant) definition.variant = options.variant;
    if (options.preview !== undefined) definition.preview = options.preview;
    if (options.clean !== undefined) definition.clean = options.clean;
    if (options.reRun !== undefined) definition.reRun = options.reRun;
    if (options.params && Object.keys(options.params).length) definition.params = options.params;
    if (options.help !== undefined) definition.help = options.help;
    if (options.inputs && Object.keys(options.inputs).length) definition.inputs = options.inputs;
    const task = new vscode.Task(definition, target.folder, `${options.help ? "Help " : options.preview ? "Dry Run " : options.clean ? "Clean " : options.reRun ? "Re-run " : ""}${title(target)}`, "project-toolkit",
      new vscode.ProcessExecution(config.executable, [...config.arguments, ...core.argsFor(target, options)], { cwd: target.root }), []);
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, clear: false, focus: target.kind === "builtin" && !options.help };
    return task;
  }

  async function run(element, preview = false, editOptional = false, cleanup = {}) {
    const target = await chooseTarget(element, editOptional);
    if (!target) return;
    let variant;
    let params = {};
    if (target.project && ["job", "workflow"].includes(target.kind)) {
      variant = variantFor(target.project);
      if (!variant && target.project.variants.some(v => !v.abstract)) {
        variant = await selectVariant(target);
        if (!variant) return;
      }
      if (target.kind === "job" && !cleanup.clean) params = await parameters(target, editOptional);
      if (params === undefined) return;
    }
    return vscode.tasks.executeTask(makeTask(target, { preview, variant, params, ...cleanup }));
  }

  function command(name, callback) {
    context.subscriptions.push(vscode.commands.registerCommand(`project-toolkit.${name}`, async (...args) => {
      try { return await callback(...args); } catch (error) {
        output.appendLine(error.message);
        await vscode.window.showErrorMessage(`Project Toolkit: ${error.message}`);
      }
    }));
  }

  command("refresh", refresh);
  command("run", element => run(element));
  command("preview", element => run(element, true));
  command("clean", element => run(element, false, false, { clean: true }));
  command("reRun", element => run(element, false, false, { reRun: true }));
  command("runWithParameters", element => run(element, false, true));
  command("showHelp", async element => {
    const target = element?.kind && element.kind !== "builtin"
      ? await chooseTarget(element) : await chooseBuiltin(element, true);
    if (target) return vscode.tasks.executeTask(makeTask(target, { help: true }));
  });
  async function runBuiltin(element, editOptional = false) {
    const target = await chooseBuiltin(element);
    if (!target) return;
    const inputs = await builtinParameters(target, editOptional);
    if (inputs === undefined) return;
    return vscode.tasks.executeTask(makeTask(target, { inputs }));
  }
  command("runBuiltin", element => runBuiltin(element));
  command("runBuiltinWithParameters", element => runBuiltin(element, true));
  command("selectVariant", selectVariant);
  command("showVariant", async element => {
    const owner = await chooseProject(element, "variants");
    if (!owner) return;
    const name = element?.name || variantFor(owner.project) || await selectVariant(owner);
    if (name) return vscode.tasks.executeTask(makeTask({ ...owner, kind: "variant", name }));
  });
  command("openReport", async element => {
    const target = await chooseTarget(element, true);
    if (!target) return;
    if (!target.project.capabilities.reports) throw new Error("Report commands are maintainer-only in this repository.");
    return vscode.tasks.executeTask(makeTask({ ...target, kind: "report" }, { variant: variantFor(target.project) }));
  });
  command("validate", async element => {
    const owner = await chooseProject(element, "validate");
    if (owner) return vscode.tasks.executeTask(makeTask({ ...owner, kind: "validate", name: "configuration" }));
  });
  command("openConfig", async element => {
    const owner = await chooseProject(element);
    if (!owner) return;
    const picked = await vscode.window.showQuickPick(owner.project.config_files.map(file => ({ label: path.relative(owner.root, file), file })), { placeHolder: "Configuration file" });
    if (picked) return vscode.commands.executeCommand("vscode.open", vscode.Uri.file(picked.file));
  });

  context.subscriptions.push(vscode.tasks.registerTaskProvider("project-toolkit", {
    async provideTasks() {
      if (!vscode.workspace.isTrusted) return [];
      await pending;
      return core.availableTargets(records).filter(t => !(t.kind === "workflow" && t.ci) && !(t.spec.params || []).some(p => p.required))
        .map(t => makeTask(t, { variant: t.project ? variantFor(t.project) : undefined }));
    },
    async resolveTask(task) {
      if (!vscode.workspace.isTrusted) return;
      await pending;
      const d = task.definition;
      const targets = d.kind === "builtin" ? core.availableBuiltins(records) : core.availableTargets(records);
      const target = targets.find(t => t.kind === d.kind && t.name === d.name && t.root === d.root);
      if (!target || target.ci && target.kind === "workflow" && !d.preview && !d.help) return;
      if (!d.help && !(d.kind === "job" && d.clean === true) && (target.spec.params || []).some(p => p.required && !Object.hasOwn(d.kind === "builtin" ? d.inputs || {} : d.params || {}, p.name))) {
        const action = d.kind === "builtin" ? "Run Command with Options" : "Run Job with Parameters";
        output.appendLine(`Use Project Toolkit: ${action} to supply required parameters for ${target.name}.`);
        return;
      }
      const resolved = makeTask(target, {
        variant: target.project ? d.variant || variantFor(target.project) : undefined,
        preview: d.preview, params: d.params, help: d.help, inputs: d.inputs, clean: d.clean, reRun: d.reRun,
      });
      resolved.definition = task.definition;
      resolved.name = task.name;
      resolved.group = task.group;
      resolved.presentationOptions = task.presentationOptions;
      resolved.runOptions = task.runOptions;
      resolved.problemMatchers = task.problemMatchers;
      return resolved;
    },
  }));
  const watcher = vscode.workspace.createFileSystemWatcher("**/{.main.ptk.yml,*.ptk.yml,*.ptk.yaml}");
  context.subscriptions.push(watcher, watcher.onDidCreate(schedule), watcher.onDidChange(schedule), watcher.onDidDelete(schedule));
  const repoWatcher = vscode.workspace.createFileSystemWatcher("**/.repo/project.list");
  context.subscriptions.push(repoWatcher, repoWatcher.onDidChange(schedule), repoWatcher.onDidCreate(schedule), repoWatcher.onDidDelete(schedule));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration("projectToolkit")) schedule(); }),
    vscode.workspace.onDidChangeWorkspaceFolders(() => schedule()), vscode.workspace.onDidGrantWorkspaceTrust(refresh),
    { dispose() { disposed = true; revision++; clearTimeout(timer); } });
  refresh();
  return { refresh, provider, ready: () => pending };
}

function activate(context) { return createController(require("vscode"), context); }
module.exports = { activate, createController };
