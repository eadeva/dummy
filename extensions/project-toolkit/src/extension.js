"use strict";

const path = require("node:path");
const core = require("./core");
const presentation = require("../media/presentation");
const { createEditors } = require("./editors");
const { validateParameters } = require("./parameters");

// Native theme colours keep the tree readable in light, dark and high contrast
// themes. Labels and icon shapes carry the same meaning without relying on colour.
const iconColors = {
  error: "errorForeground", warning: "list.warningForeground",
  repo: "charts.blue", "root-folder": "charts.blue", project: "charts.blue",
  "play-circle": "charts.green", tasklist: "charts.green", check: "charts.green",
  "git-merge": "charts.purple", layers: "charts.orange", versions: "charts.orange",
  "settings-gear": "charts.yellow", folder: "charts.yellow", key: "charts.yellow",
  package: "charts.orange", tools: "charts.orange", calendar: "charts.purple",
  terminal: "charts.blue", "symbol-variable": "charts.blue", "symbol-object": "charts.purple",
  "list-tree": "charts.purple", "list-ordered": "charts.purple", "list-unordered": "charts.purple",
  output: "charts.blue", graph: "charts.green", question: "charts.blue", sync: "charts.blue",
};

// VS Code is injected so command dispatch and trust boundaries can be tested
// without pretending a mock is a graphical extension-host acceptance test.
function createController(vscode, context, editorFactory = createEditors) {
  let records = [];
  let revision = 0;
  let timer;
  let disposed = false;
  let loading = false;
  let pending = Promise.resolve();
  const changed = new vscode.EventEmitter();
  const output = vscode.window.createOutputChannel("Project Toolkit");
  context.subscriptions.push(changed, output);
  const diagnostics = vscode.languages?.createDiagnosticCollection("ptk");
  if (diagnostics) context.subscriptions.push(diagnostics);
  const editors = editorFactory(vscode, context, {
    changed: () => schedule(),
    validate: async uri => validateConfiguration({ configFile: uri.fsPath }),
    project: async (entry, { publish = true } = {}) => {
      if (publish) await refresh();
      else {
        await settled();
        const record = records.find(record => record.inventory?.projects.some(project => project.entry_file === entry));
        if (!record) throw new Error("PTK project is no longer available.");
        const inventory = await core.readInventory(settings(record.folder), record.folder.uri.fsPath);
        const project = inventory.projects.find(project => project.entry_file === entry);
        if (!project) throw new Error("PTK project is no longer available.");
        return { project, folder: record.folder, root: project.root };
      }
      for (const record of records) {
        const project = record.inventory?.projects.find(project => project.entry_file === entry);
        if (project) return { project, folder: record.folder, root: project.root };
      }
      throw new Error("PTK project is no longer available.");
    },
    configuration: async uri => {
      await settled();
      return records.flatMap(record => record.inventory?.projects || [])
        .find(project => project.config_files?.includes(uri.fsPath))?.configuration;
    },

  });

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
    // Coalesce refreshes and wait for the previous process instead of starting
    // overlapping CLI instances while files are being installed or generated.
    pending = pending.then(async () => {
      if (current !== revision || disposed || !vscode.workspace.isTrusted) return;
      loading = true;
      if (!records.length) changed.fire();
      const folders = (vscode.workspace.workspaceFolders || []).filter(folder => folder.uri.scheme === "file");
      const result = await Promise.all(folders.map(async folder => {
        try {
          return { folder, inventory: await core.readInventory(settings(folder), folder.uri.fsPath) };
        } catch (error) {
          const previous = records.find(record => record.folder.uri.fsPath === folder.uri.fsPath);
          return { folder, error: error.message, previous: previous?.inventory || previous?.previous };
        }
      }));
      if (current !== revision || disposed || !vscode.workspace.isTrusted) return;
      const content = items => JSON.stringify(items.map(({ folder, ...record }) => [folder.uri.fsPath, record]));
      const different = content(records) !== content(result);
      records = result;
      loading = false;
      diagnostics?.clear();
      const byFile = new Map();
      for (const project of records.flatMap(record => record.inventory?.projects || [])) {
        for (const issue of project.diagnostics || []) {
          if (!diagnostics) continue;
          const line = Math.max(0, (issue.line || 1) - 1);
          const items = byFile.get(issue.file) || [];
          items.push(new vscode.Diagnostic(new vscode.Range(line, 0, line, 1), `${issue.path ? `${issue.path}: ` : ""}${issue.message}`, vscode.DiagnosticSeverity.Error));
          byFile.set(issue.file, items);
        }
      }
      for (const [file, items] of byFile) diagnostics.set(vscode.Uri.file(file), items);
      for (const record of records) {
        if (record.error) output.appendLine(`${record.folder.name}: ${record.error}`);
      }
      if (different) changed.fire();
    });
    return settled();
  }

  async function settled() {
    // A watcher may supersede discovery while it is in flight. Consumers must
    // wait for the replacement too, rather than acknowledge an older inventory.
    let observed;
    do { observed = pending; await observed; } while (observed !== pending);
  }

  function schedule(uri) {
    if (uri && core.ignoreConfigEvent(uri.fsPath,
      (vscode.workspace.workspaceFolders || []).map(folder => folder.uri.fsPath),
      records.flatMap(record => (record.inventory?.projects || []).flatMap(project => project.config_files || [])))) return;
    clearTimeout(timer);
    timer = setTimeout(refresh, 350);
  }

  const variantKey = target => `variant:${target.project.entry_file}:${target.kind}:${target.name}`;
  const variantFor = target => core.selectedVariant(target.project, context.workspaceState.get(variantKey(target)));
  const targetNodes = new Map();
  const title = target => `${target.project?.alias || path.basename(target.root)} / ${target.kind} / ${target.name}`;

  function variantChildren(target) {
    const variants = target.project.variants.filter(item => !item.abstract);
    if (!variants.length) return [];
    return [
      { label: "Use project default", variantName: undefined, description: target.project.default_variant || "No default configured" },
      ...variants.map(item => ({ label: item.name, name: item.name, variantName: item.name, description: item.description })),
    ].map(item => ({
      ...item, project: target.project, folder: target.folder, root: target.root,
      kind: "variant-choice", target, icon: "layers",
      contextValue: item.variantName ? "variant" : "variant-default",
      id: JSON.stringify([target.folder.uri.fsPath, variantKey(target), "choice", item.variantName ?? null]),
      tooltip: [item.description, `Select one variant for ${target.kind} ${target.name}. Other jobs and workflows keep their own selection.`].filter(Boolean).join("\n"),
    }));
  }

  function variantChanged(target) {
    // Only refresh the affected job/workflow, keeping the configuration editor
    // and other expanded branches undisturbed. No PTK discovery is needed.
    changed.fire(targetNodes.get(variantKey(target)));
  }

  async function changeVariantCheckboxes(event) {
    trusted();
    await settled();
    const choices = new Map();
    for (const [element, state] of event.items) {
      if (element.kind !== "variant-choice") continue;
      const key = variantKey(element.target);
      const previous = choices.get(key);
      // A checked option wins if VS Code delivers sibling updates together.
      if (!previous || state === vscode.TreeItemCheckboxState.Checked) choices.set(key, { element, state });
    }
    for (const { element, state } of choices.values()) {
      const target = await chooseTarget(element.target);
      const checked = state === vscode.TreeItemCheckboxState.Checked;
      const name = checked ? element.variantName : undefined;
      if (name && !target.project.variants.some(item => !item.abstract && item.name === name)) {
        throw new Error("This variant is no longer available. Refresh projects and choose a variant.");
      }
      const saved = context.workspaceState.get(variantKey(target));
      if (checked || saved === element.variantName) await context.workspaceState.update(variantKey(target), name);
      variantChanged(target);
    }
  }

  function builtinTree(owner, commands) {
    // Dedicated job/workflow actions replace these generic tree entries only.
    // Keep the full inventory for CLI help, the command palette and saved tasks.
    function visible(items) {
      return items.filter(spec => !["run", "dry-run", "report"].includes(spec.path[0]) &&
        !(spec.path[0] === "workflow" && ["run", "dry-run", "report"].includes(spec.path[1])))
        .map(spec => ({ ...spec, children: visible(spec.children) }))
        .filter(spec => spec.runnable || spec.children.length);
    }
    const treeCommands = visible(commands);
    const targets = core.builtinTargets(owner, treeCommands);
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
    const children = [help, ...treeCommands.map(spec => nodes.get(spec.path.join(" ")))];
    return { label: "Built-in commands", children, icon: "terminal" };
  }

  function validationNode(owner = {}) {
    return { ...owner, label: "Validate configuration", icon: "check",
      command: { command: "project-toolkit.validate", title: "Validate configuration", arguments: [owner] } };
  }

  function configurationNode(common) {
    const config = common.project.configuration;
    const sources = new Map(config.sources.map(source => [JSON.stringify(source.path), source]));
    function field(value, configPath, label) {
      const name = presentation.namedEntry(value, configPath);
      if (name) return field(value[name], [...configPath, name], name);
      const source = sources.get(JSON.stringify(configPath));
      const object = value !== null && typeof value === "object";
      const node = { ...common, kind: "configuration", configPath, label,
        id: JSON.stringify([common.folder.uri.fsPath, common.project.entry_file, "configuration", configPath]),
        collapsed: true, icon: presentation.icon(value, configPath),
        tooltip: source ? `${source.file}:${source.line}` : "Not configured",
        description: value === undefined ? "not configured" : object || typeof configPath.at(-1) === "number" ? "" : String(value),
      };
      if (object) node.children = Object.entries(value).filter(([key]) => !(key === "components" && configPath.length === 1 && ["project", "variants"].includes(configPath[0]))).map(([key, child]) => field(child, [...configPath, Array.isArray(value) ? Number(key) : key], Array.isArray(value) ? presentation.listLabel(child, [...configPath, Number(key)]) : key));
      node.command = { command: "project-toolkit.openConfig", title: "Edit configuration", arguments: [node] };
      return node;
    }
    const value = config.value || {};
    const keys = [...new Set([...Object.keys(config.schema.properties || {}).filter(key => key !== "members"), ...Object.keys(value)])];
    const node = field(value, [], "Configuration");
    node.children = keys.map(key => field(value[key], [key], key));
    const components = field(value.project?.components || {}, ["project", "components"], "Components");
    components.icon = "package";
    components.children = Object.keys(value.project?.components || {}).map(name => {
      const component = field(value.variants?.components?.[name] || {}, ["variants", "components", name], name);
      component.children = [field(value.project.components[name].path, ["project", "components", name, "path"], "Directory"), ...(component.children || [])];
      return component;
    });
    node.children.push(components);
    return node;
  }

  function projectNode(project, record) {
    const common = { project, folder: record.folder, root: project.root, ci: record.inventory.ci };
    const groups = [validationNode(common)];
    if (project.error) {
      groups.push(...(project.diagnostics || [{ message: project.error, file: project.entry_file }]).map(issue => ({
        label: issue.message, description: issue.path, tooltip: `${issue.file}:${issue.line || 1}`, icon: "error",
        command: { command: "vscode.open", title: "Open configuration error", arguments: [vscode.Uri.file(issue.file), { selection: vscode.Range ? new vscode.Range((issue.line || 1) - 1, 0, (issue.line || 1) - 1, 0) : undefined }] },
      })));
      groups.push(configurationNode(common));
      return { ...common, label: project.alias, description: "configuration error", tooltip: project.error, icon: "error", children: groups };
    }
    for (const kind of ["job", "workflow"]) {
      const children = project[`${kind}s`].map(spec => {
        const target = { ...common, kind, name: spec.name, spec };
        const node = { ...target, label: spec.name, tooltip: spec.help,
          contextValue: core.canOpenReport(target) ? `${kind}-report` : kind,
          description: [variantFor(target), kind === "workflow" && common.ci ? "dry-run only on CI" : spec.default ? "default" : ""].filter(Boolean).join(" · "),
          icon: kind === "job" ? "play-circle" : "git-merge",
          collapsed: true, children: variantChildren(target),
        };
        const nodes = targetNodes.get(variantKey(target)) || [];
        nodes.push(node);
        targetNodes.set(variantKey(target), nodes);
        return node;
      });
      if (children.length) groups.push({ label: kind === "job" ? "Jobs" : "Workflows", icon: kind === "job" ? "tasklist" : "git-merge", children });
    }
    groups.push(builtinTree(common, project.commands), configurationNode(common));
    return { ...common, label: project.alias, description: project.name, tooltip: project.root,
      contextValue: "project", icon: "repo", children: groups };
  }

  function identified(node, parent) {
    const parts = [...parent, node.kind || "group", node.name || node.label];
    node.id ||= JSON.stringify(parts);
    for (const child of node.children || []) identified(child, parts);
    return node;
  }

  const provider = {
    onDidChangeTreeData: changed.event,
    getChildren(element) {
      if (element) return element.children || [];
      targetNodes.clear();
      if (loading && !records.length) return [{ label: "Loading PTK configuration…", icon: "sync" }];
      return records.map(record => identified((() => {
        if (record.error) return {
          label: record.folder.name, description: "PTK unavailable", tooltip: `${record.error}\nClick to show the discovery error.`, icon: "warning",
          command: { command: "project-toolkit.showOutput", title: "Show PTK Discovery Error" },
          children: [validationNode({ folder: record.folder, root: record.folder.uri.fsPath }),
            ...(record.previous?.projects || []).map(project => projectNode({ ...project, error: record.error }, { ...record, inventory: record.previous }))],
        };
        const children = record.inventory.projects.map(project => projectNode(project, record));
        if (!children.length) children.push(validationNode({ folder: record.folder, root: record.folder.uri.fsPath }));
        if (record.inventory.workflows.length) children.unshift({ label: "Workspace workflows", icon: "git-merge", children: record.inventory.workflows.map(spec => ({
          kind: "workflow", name: spec.name, spec, root: record.inventory.root, folder: record.folder, ci: record.inventory.ci,
          label: spec.name, tooltip: spec.help, icon: "git-merge",
          contextValue: core.canOpenReport({ kind: "workflow", commands: record.inventory.commands }) ? "workflow-report" : "workflow",
        })) });
        if (record.inventory.mode === "workspace") children.push(builtinTree({ root: record.inventory.root, folder: record.folder, ci: record.inventory.ci }, record.inventory.commands));
        return { label: record.folder.name, description: record.inventory.mode === "workspace" ? "VMR" : "", children, icon: "root-folder" };
      })(), [record.folder.uri.fsPath]));
    },
    getTreeItem(element) {
      const item = new vscode.TreeItem(element.label, element.children?.length || element.hasChildren
        ? element.collapsed ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None);
      item.id = element.id;
      item.description = element.description;
      item.tooltip = element.tooltip;
      item.contextValue = element.contextValue;
      item.command = element.command;
      if (["job", "workflow"].includes(element.kind) && element.project) {
        item.description = [variantFor(element), element.kind === "workflow" && element.ci ? "dry-run only on CI" : element.spec.default ? "default" : ""].filter(Boolean).join(" · ");
      }
      if (element.kind === "variant-choice") {
        const saved = context.workspaceState.get(variantKey(element.target));
        const validSaved = element.project.variants.some(item => !item.abstract && item.name === saved) ? saved : undefined;
        item.checkboxState = {
          state: validSaved === element.variantName ? vscode.TreeItemCheckboxState.Checked : vscode.TreeItemCheckboxState.Unchecked,
          tooltip: element.tooltip,
          accessibilityInformation: { label: `${element.label}, variant for ${element.target.kind} ${element.target.name}` },
        };
      }
      if (element.icon) item.iconPath = new vscode.ThemeIcon(
        element.icon, iconColors[element.icon] ? new vscode.ThemeColor(iconColors[element.icon]) : undefined
      );
      return item;
    },
  };
  const tree = vscode.window.createTreeView("project-toolkit.projects", { treeDataProvider: provider, manageCheckboxStateManually: true });
  let checkboxChanges = Promise.resolve();
  context.subscriptions.push(tree, tree.onDidChangeCheckboxState(event => {
    checkboxChanges = checkboxChanges.then(() => changeVariantCheckboxes(event)).catch(async error => {
      changed.fire();
      await vscode.window.showErrorMessage(error.message);
    });
    return checkboxChanges;
  }));

  async function chooseProject(element, capability) {
    trusted();
    await settled();
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
    await settled();
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
    await settled();
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
    const target = await chooseTarget(element);
    if (!target) return;
    if (!target.project) {
      await vscode.window.showInformationMessage("Workspace workflows use the variants configured on their repository steps.");
      return;
    }
    const choices = target.project.variants.filter(v => !v.abstract);
    const selected = await vscode.window.showQuickPick([
      { label: "Use project default", description: target.project.default_variant || "No default configured", reset: true },
      ...choices.map(v => ({ label: v.name, description: v.description, name: v.name })),
    ], { placeHolder: `Variant for ${target.kind} ${target.name}${target.kind === "workflow" ? " (repository mappings apply)" : ""}` });
    if (!selected) return;
    await context.workspaceState.update(variantKey(target), selected.reset ? undefined : selected.name);
    variantChanged(target);
    return variantFor(target);
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
    if (options.report && !core.canOpenReport(target)) throw new Error("Report opening is unavailable. Check PTK's version and command permissions.");
    if (target.kind === "workflow" && target.ci && !options.preview && !options.help && !options.report) throw new Error("Workflows run locally only; CI can dry-run workflows or run individual jobs.");
    const definition = { type: "project-toolkit", kind: target.kind, name: target.name, root: target.root };
    if (options.variant) definition.variant = options.variant;
    if (options.preview !== undefined) definition.preview = options.preview;
    if (options.clean !== undefined) definition.clean = options.clean;
    if (options.reRun !== undefined) definition.reRun = options.reRun;
    if (options.params && Object.keys(options.params).length) definition.params = options.params;
    if (options.help !== undefined) definition.help = options.help;
    if (options.report !== undefined) definition.report = options.report;
    if (options.inputs && Object.keys(options.inputs).length) definition.inputs = options.inputs;
    const task = new vscode.Task(definition, target.folder, `${options.report ? "Report " : options.help ? "Help " : options.preview ? "Dry Run " : options.clean ? "Clean " : options.reRun ? "Re-run " : ""}${title(target)}`, "project-toolkit",
      new vscode.ProcessExecution(config.executable, core.launchArgs(config, core.argsFor(target, options)), { cwd: target.root }), []);
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, clear: false, focus: target.kind === "builtin" && !options.help };
    return task;
  }

  async function run(element, preview = false, editOptional = false, cleanup = {}) {
    const target = await chooseTarget(element, editOptional);
    if (!target) return;
    let variant;
    let params = {};
    if (target.project && ["job", "workflow"].includes(target.kind)) {
      variant = variantFor(target);
      if (!variant && target.project.variants.some(v => !v.abstract)) {
        variant = await selectVariant(target);
        if (!variant) return;
      }
      if (target.kind === "job" && !cleanup.clean && (editOptional || (target.spec.params || []).some(spec => spec.required))) {
        const result = await editors.parameters(target, { preview, variant, ...cleanup });
        if (!result) return;
        params = result.params;
        preview = result.preview;
      }
    }
    // A form may remain open while discovery, permissions or the configuration changes.
    const current = await chooseTarget(target);
    if (current.kind === "job" && !cleanup.clean) validateParameters(current.spec.params || [], params);
    if (variant && current.project && !current.project.variants.some(item => item.name === variant && !item.abstract)) throw new Error("This variant is no longer available. Refresh projects and choose a variant.");
    return vscode.tasks.executeTask(makeTask(current, { preview, variant, params, ...cleanup }));
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
  command("showOutput", () => output.show(true));
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
    const name = element?.name || core.selectedVariant(owner.project) || await selectVariant(owner);
    if (name) return vscode.tasks.executeTask(makeTask({ ...owner, kind: "variant", name }));
  });
  command("openReport", async element => {
    const target = await chooseTarget(element);
    if (!target) return;
    return vscode.tasks.executeTask(makeTask(target, {
      report: true, variant: target.kind === "job" ? variantFor(target) : undefined,
    }));
  });
  async function validateConfiguration(element = {}) {
    trusted();
    await settled();
    const candidates = records.flatMap(record => ((record.inventory || record.previous)?.projects || [])
      .map(project => ({ project, folder: record.folder, root: project.root })));
    let owner = candidates.find(candidate => element.project?.entry_file === candidate.project.entry_file ||
      element.configFile && (candidate.project.config_files?.includes(element.configFile) || element.configFile === candidate.project.entry_file));
    if (!owner && candidates.length === 1) owner = candidates[0];
    if (!owner && candidates.length > 1) {
      owner = (await vscode.window.showQuickPick(candidates.map(owner => ({ label: owner.project.alias, description: owner.root, owner })), { placeHolder: "Validate PTK repository" }))?.owner;
      if (!owner) return;
    }
    if (owner) return vscode.tasks.executeTask(makeTask({ ...owner, kind: "validate", name: "configuration" }));
    const folder = element.folder || vscode.workspace.workspaceFolders?.[0];
    const record = records.find(record => record.folder === folder);
    if (record?.error) {
      // Let PTK report the actual loading/runtime error; a discovery failure is
      // not evidence that there is no project.
      return vscode.tasks.executeTask(makeTask({ folder, root: folder.uri.fsPath, kind: "validate", name: "configuration" }));
    }
    const action = await vscode.window.showInformationMessage("No PTK project found (.main.ptk.yml).", "PTK setup init");
    if (action === "PTK setup init") return initializeProject(folder);
  }
  async function initializeProject(folder) {
    trusted();
    folder = folder || vscode.workspace.workspaceFolders?.[0];
    if (!folder) { await vscode.window.showInformationMessage("Open a folder before running PTK setup init."); return; }
    const configDir = await vscode.window.showInputBox({ title: "PTK setup init", prompt: "Configuration folder relative to the repository root", value: "config/ptk" });
    if (!configDir?.trim()) return;
    return vscode.tasks.executeTask(makeTask({ folder, root: folder.uri.fsPath, kind: "init", name: "project" }, { configDir: configDir.trim() }));
  }
  command("validate", validateConfiguration);
  command("init", () => initializeProject());
  command("openConfig", async element => {
    trusted();
    const owner = element?.project ? element : await chooseProject(element);
    if (owner) return editors.openProject(owner, element?.configPath || []);
  });

  command("openConfigForm", async uri => {
    trusted();
    uri = uri || vscode.window.activeTextEditor?.document.uri;
    if (uri?.scheme === "file") return editors.open(uri);
  });

  context.subscriptions.push(vscode.tasks.registerTaskProvider("project-toolkit", {
    async provideTasks() {
      if (!vscode.workspace.isTrusted) return [];
      await settled();
      return core.availableTargets(records).filter(t => !(t.kind === "workflow" && t.ci) && !(t.spec.params || []).some(p => p.required && !p.env))
        .map(t => makeTask(t, { variant: t.project ? variantFor(t) : undefined }));
    },
    async resolveTask(task) {
      if (!vscode.workspace.isTrusted) return;
      await settled();
      const d = task.definition;
      const targets = d.kind === "builtin" ? core.availableBuiltins(records) : core.availableTargets(records);
      const target = targets.find(t => t.kind === d.kind && t.name === d.name && t.root === d.root);
      if (!target || d.report && !core.canOpenReport(target) || target.ci && target.kind === "workflow" && !d.preview && !d.help && !d.report) return;
      if (!d.report && !d.help && !(d.kind === "job" && d.clean === true) && (target.spec.params || []).some(p => p.required && !p.env && !Object.hasOwn(d.kind === "builtin" ? d.inputs || {} : d.params || {}, p.name))) {
        const action = d.kind === "builtin" ? "Run Command with Options" : "Run Job with Parameters";
        output.appendLine(`Use Project Toolkit: ${action} to supply required parameters for ${target.name}.`);
        return;
      }
      const resolved = makeTask(target, {
        variant: target.project && !d.help ? d.variant || variantFor(target) : undefined,
        preview: d.preview, params: d.params, help: d.help, inputs: d.inputs, clean: d.clean, reRun: d.reRun, report: d.report,
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
  context.subscriptions.push(vscode.tasks.onDidEndTaskProcess(event => {
    if (event.execution.task.definition.type === "project-toolkit") schedule();
  }));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration("projectToolkit")) schedule(); }),
    vscode.workspace.onDidChangeWorkspaceFolders(() => schedule()), vscode.workspace.onDidGrantWorkspaceTrust(refresh),
    { dispose() { disposed = true; revision++; clearTimeout(timer); } });
  refresh();
  return { refresh, provider, ready: settled };
}

function activate(context) { return createController(require("vscode"), context); }
module.exports = { activate, createController };
