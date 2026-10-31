"use strict";

const path = require("node:path");
const core = require("./core");
const presentation = require("../media/presentation");
const schemaTools = require("../media/schema");
const { createEditors } = require("./editors");
const { validateParameters } = require("./parameters");
const { canonicalPath } = require("./file-path");

// Native theme colours keep the tree readable in light, dark and high contrast
// themes. Labels and icon shapes carry the same meaning without relying on colour.
const entityColors = { workflow: "charts.purple", job: "charts.blue", gui: "terminal.ansiCyan", step: "descriptionForeground", builtin: "descriptionForeground" };
const iconColors = {
  error: "errorForeground", warning: "list.warningForeground",
  repo: "foreground", "root-folder": "foreground", project: "foreground",
  "play-circle": "charts.blue", tasklist: "charts.blue", window: "terminal.ansiCyan", check: "charts.green",
  "git-merge": "charts.purple", layers: "charts.orange", versions: "charts.orange",
  "settings-gear": "foreground", folder: "foreground", key: "foreground",
  package: "foreground", tools: "foreground", calendar: "charts.purple",
  terminal: "descriptionForeground", "symbol-variable": "descriptionForeground", "symbol-object": "descriptionForeground",
  "symbol-field": "descriptionForeground", "list-tree": "descriptionForeground", "list-ordered": "descriptionForeground", "list-unordered": "descriptionForeground",
  output: "descriptionForeground", graph: "charts.blue", question: "descriptionForeground", sync: "descriptionForeground",
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
      const file = canonicalPath(uri.fsPath);
      return records.flatMap(record => record.inventory?.projects || [])
        .find(project => project.config_files?.some(candidate => canonicalPath(candidate) === file))?.configuration;
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
  const explicitVariants = target => {
    const saved = context.workspaceState.get(variantKey(target));
    const names = Array.isArray(saved) ? saved : [];
    return [...new Set(names)].filter(name => target.project.variants.some(item => !item.abstract && item.name === name));
  };
  const variantsFor = target => {
    const names = explicitVariants(target);
    if (names.length) return names;
    const defaultVariant = core.selectedVariant(target.project);
    return defaultVariant ? [defaultVariant] : [];
  };
  const variantDescription = target => variantsFor(target).join(", ");
  const targetNodes = new Map();
  const title = target => `${target.project?.alias || path.basename(target.root)} / ${target.spec?.gui ? "GUI" : target.kind} / ${target.name}`;

  function variantChildren(target) {
    const variants = target.project.variants.filter(item => !item.abstract);
    if (!variants.length) return [];
    return [
      { label: "All variants", allVariants: true, description: "Run all concrete variants in parallel" },
      ...variants.map(item => ({ label: item.name, name: item.name, variantName: item.name, description: item.description })),
    ].map(item => ({
      ...item, project: target.project, folder: target.folder, root: target.root,
      kind: "variant-choice", target, icon: "layers",
      contextValue: item.allVariants ? "variant-all" : "variant",
      id: JSON.stringify([target.folder.uri.fsPath, variantKey(target), "choice", item.variantName ?? null]),
      tooltip: [item.description, `Select variants for ${target.kind} ${target.name}. Selected variants run in parallel. Clearing the selection selects the project default automatically.`].filter(Boolean).join("\n"),
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
      const updates = choices.get(key) || [];
      updates.push({ element, state });
      choices.set(key, updates);
    }
    for (const updates of choices.values()) {
      const target = await chooseTarget(updates[0].element.target);
      const names = new Set(variantsFor(target));
      for (const { element, state } of updates) {
        const checked = state === vscode.TreeItemCheckboxState.Checked;
        const name = element.variantName;
        if (checked && name && !target.project.variants.some(item => !item.abstract && item.name === name)) {
          throw new Error("This variant is no longer available. Refresh projects and choose a variant.");
        }
        if (element.allVariants) {
          names.clear();
          if (checked) for (const variant of target.project.variants) if (!variant.abstract) names.add(variant.name);
        } else if (checked) names.add(name);
        else names.delete(name);
      }
      await context.workspaceState.update(variantKey(target), names.size ? [...names] : undefined);
      variantChanged(target);
    }
  }

  function builtinTree(owner, commands) {
    // Dedicated job/workflow actions replace these generic tree entries only.
    // Keep the full inventory for CLI help, the command palette and saved tasks.
    function visible(items) {
      return items.filter(spec => {
        const path = spec.path[0] === "maintainer" ? spec.path.slice(1) : spec.path;
        return !["run", "report"].includes(path[0]) && !(path[0] === "workflow" && path[1] === "run");
      })
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
    return { label: "Built-in commands", children, icon: "terminal", entityKind: "builtin" };
  }

  function validationNode(owner = {}) {
    return { ...owner, label: "Validate configuration", icon: "check", entityKind: "builtin",
      command: { command: "project-toolkit.validate", title: "Validate configuration", arguments: [owner] } };
  }

  function configurationNode(common) {
    const config = common.project.configuration;
    const sources = new Map(config.sources.map(source => [JSON.stringify(source.path), source]));
    function field(value, configPath, label) {
      const source = sources.get(JSON.stringify(configPath));
      const object = value !== null && typeof value === "object";
      const node = { ...common, kind: "configuration", configPath, label,
        id: JSON.stringify([common.folder.uri.fsPath, common.project.entry_file, "configuration", configPath]),
        collapsed: true, icon: presentation.icon(value, configPath), entityKind: presentation.entity(configPath, { logical: true, value: config.value }),
        tooltip: source ? `${source.file}:${source.line}` : "Not configured",
        description: value === undefined ? "not configured" : object || typeof configPath.at(-1) === "number" ? "" : String(value),
      };
      if (object) node.children = schemaTools.orderedEntries(schemaTools.at(config.schema, config.value, configPath, config.schema), value, config.schema).filter(([key]) => !(key === "components" && configPath.length === 1 && ["project", "variants"].includes(configPath[0]))).map(([key, child]) => field(child, [...configPath, Array.isArray(value) ? Number(key) : key], Array.isArray(value) ? presentation.listLabel(child, [...configPath, Number(key)]) : key));
      const graph = config.graphs.find(item => JSON.stringify(item.path) === JSON.stringify(configPath));
      if (graph && !graph.error) {
        node.icon = "git-merge";
        node.description = "prerequisites → dependents";
        node.tooltip = "Expand a prerequisite to see its dependents. Joins wait for all prerequisites; branches can overlap. Shared references edit the same definition.";
        node.children = [];
        const metadata = new Map(graph.nodes.map(item => [item.id, item]));
        const branches = [];
        for (const [index, entry] of graph.tree.entries()) {
          const item = metadata.get(entry.id);
          const child = field(value[item.id], [...configPath, item.id], item.id);
          child.id = `${node.id}:branch:${index}`;
          child.icon = entry.shared ? "references" : "git-branch";
          child.description = [item.label !== item.id ? item.label : "", item.needs.length > 1 ? `needs all: ${item.needs.join(", ")}` : "", entry.shared ? "↩ shared — shown above" : ""].filter(Boolean).join(" · ");
          child.tooltip = `${item.label ? item.label + "\n" : ""}Needs: ${item.needs.join(", ") || "none"}\n${entry.shared ? "Shared dependency; edits the same definition.\n" : ""}${child.tooltip}`;
          child.children = [];
          branches.push(child);
          (entry.parent === null ? node : branches[entry.parent]).children.push(child);
        }
      } else if (graph?.error) {
        node.description = "invalid graph";
        node.tooltip = graph.error;
      }
      node.command = { command: "project-toolkit.openConfig", title: "Edit configuration", arguments: [node] };
      return node;
    }
    const value = config.value || {};
    const keys = schemaTools.orderedEntries(config.schema, value, config.schema, { includeMissing: true }).map(([key]) => key).filter(key => key !== "members" || Object.hasOwn(value, key));
    const node = field(value, [], "Configuration");
    node.children = keys.map(key => field(value[key], [key], key));
    const components = field(value.project?.components || {}, ["project", "components"], "Components");
    components.icon = "package";
    components.children = Object.keys(value.project?.components || {}).map(name => {
      const component = field(value.variants?.components?.[name] || {}, ["variants", "components", name], name);
      component.children = [field(value.project.components[name].path, ["project", "components", name, "path"], "Directory"), ...(component.children || [])];
      return component;
    });
    const variantsIndex = node.children.findIndex(child => child.configPath[0] === "variants");
    const projectIndex = node.children.findIndex(child => child.configPath[0] === "project");
    node.children.splice(Math.max(variantsIndex, projectIndex) + 1, 0, components);
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
    for (const group of ["job", "gui", "workflow"]) {
      const kind = group === "gui" ? "job" : group;
      const children = project[`${kind}s`].filter(spec => kind !== "job" || Boolean(spec.gui) === (group === "gui")).map(spec => {
        const target = { ...common, kind, name: spec.name, spec };
        const node = { ...target, entityKind: group, label: spec.name, tooltip: [spec.help, spec.gui ? "Launch GUI: preparation finishes first, then the application runs independently of PTK." : ""].filter(Boolean).join("\n"),
          contextValue: core.canOpenReport(target) ? `${kind}-report` : kind,
          description: [variantDescription(target), kind === "workflow" && common.ci ? "dry-run only on CI" : spec.default ? "default" : ""].filter(Boolean).join(" · "),
          icon: group === "gui" ? "window" : kind === "job" ? "play-circle" : "git-merge",
          collapsed: true, children: variantChildren(target),
        };
        const nodes = targetNodes.get(variantKey(target)) || [];
        nodes.push(node);
        targetNodes.set(variantKey(target), nodes);
        return node;
      });
      if (children.length) groups.push({ entityKind: group, label: group === "gui" ? "GUIs" : kind === "job" ? "Jobs" : "Workflows", icon: group === "gui" ? "window" : kind === "job" ? "tasklist" : "git-merge", children });
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
        if (record.inventory.workflows.length) children.unshift({ label: "Workspace workflows", entityKind: "workflow", icon: "git-merge", children: record.inventory.workflows.map(spec => ({
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
        item.description = [variantDescription(element), element.kind === "workflow" && element.ci ? "dry-run only on CI" : element.spec.default ? "default" : ""].filter(Boolean).join(" · ");
      }
      if (element.kind === "variant-choice") {
        const selected = variantsFor(element.target);
        const checked = element.allVariants ? element.target.project.variants.filter(variant => !variant.abstract).every(variant => selected.includes(variant.name)) : selected.includes(element.variantName);
        item.checkboxState = {
          state: checked ? vscode.TreeItemCheckboxState.Checked : vscode.TreeItemCheckboxState.Unchecked,
          tooltip: element.tooltip,
          accessibilityInformation: { label: `${element.label}, variant for ${element.target.kind} ${element.target.name}` },
        };
      }
      const color = entityColors[element.entityKind || element.kind] || iconColors[element.icon];
      if (element.icon) item.iconPath = new vscode.ThemeIcon(
        element.icon, color ? new vscode.ThemeColor(color) : undefined
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
      await vscode.window.showInformationMessage("Workspace workflows have no variant selection. Use a repository-owned workflow for variant-enabled jobs.");
      return;
    }
    const choices = target.project.variants.filter(v => !v.abstract);
    const current = variantsFor(target);
    const selected = await vscode.window.showQuickPick([
      { label: "All variants", description: "Run all concrete variants in parallel", all: true },
      ...choices.map(v => ({ label: v.name, description: v.description, name: v.name, picked: current.includes(v.name) })),
    ], { canPickMany: true, placeHolder: `Variants for ${target.kind} ${target.name} · run in parallel · clear to select the project default` });
    if (!selected) return;
    const names = selected.some(item => item.all) ? choices.map(item => item.name) : selected.map(item => item.name);
    await context.workspaceState.update(variantKey(target), names.length ? names : undefined);
    variantChanged(target);
    return variantsFor(target);
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
          const value = choices.length ? (await vscode.window.showQuickPick(choices.map(value => ({ label: value, value, description: param.suggestions?.find(item => item.value === value)?.help || param.help })), { title: prompt, placeHolder: param.help || "Choose a value" }))?.value
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
    if (options.runOptions && Object.keys(options.runOptions).length) definition.runOptions = options.runOptions;
    const task = new vscode.Task(definition, target.folder, `${options.report ? "Report " : options.help ? "Help " : options.preview ? "Dry Run " : options.clean ? "Clean " : options.reRun ? "Re-run " : ""}${title(target)}${options.variant ? ` [${options.variant}]` : ""}`, "project-toolkit",
      new vscode.ProcessExecution(config.executable, core.launchArgs(config, core.argsFor(target, options)), { cwd: core.cwdFor(target) }), []);
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, clear: false, focus: target.kind === "builtin" && !options.help };
    return task;
  }

  async function run(element, preview = false, editOptional = false, cleanup = {}) {
    const target = await chooseTarget(element);
    if (!target) return;
    let variants = target.project ? variantsFor(target) : [];
    let params = {}, runOptions = {};
    const form = !cleanup.clean && (editOptional || (target.spec.params || []).some(spec => spec.required));
    if (form) {
      const result = await editors.parameters(target, {
        preview, variant: variants.length === 1 ? variants[0] : undefined, variants,
        ...cleanup,
      });
      if (!result) return;
      params = result.params;
      preview = result.preview;
      runOptions = result.runOptions || {};
      if (result.variants !== undefined) variants = result.variants.length ? result.variants : (target.project?.default_variant ? [target.project.default_variant] : []);
    } else if (target.project && !variants.length && target.project.variants.some(v => !v.abstract)) {
      variants = await selectVariant(target);
      if (!variants?.length) return;
    }
    // Recheck choices and permissions after a form that may have stayed open during edits.
    const current = await chooseTarget(target);
    if (current.kind === "job" && !cleanup.clean) validateParameters(current.spec.params || [], params);
    if (variants.some(variant => !current.project?.variants.some(item => item.name === variant && !item.abstract))) throw new Error("A selected variant is no longer available. Refresh projects and choose variants.");
    const tasks = (variants.length ? variants : [undefined]).map(variant => makeTask(current, { preview, variant, params, runOptions, ...cleanup }));
    return Promise.all(tasks.map(task => vscode.tasks.executeTask(task)));
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
    const name = element?.name || core.selectedVariant(owner.project) || (await vscode.window.showQuickPick(owner.project.variants.filter(item => !item.abstract).map(item => ({ label: item.name, name: item.name })), { placeHolder: "Display variant" }))?.name;
    if (name) return vscode.tasks.executeTask(makeTask({ ...owner, kind: "variant", name }));
  });
  command("openReport", async element => {
    const target = await chooseTarget(element);
    if (!target) return;
    const variants = target.kind === "job" ? variantsFor(target) : [];
    const tasks = (variants.length ? variants : [undefined]).map(variant => makeTask(target, { report: true, variant }));
    return Promise.all(tasks.map(task => vscode.tasks.executeTask(task)));
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
    const action = await vscode.window.showInformationMessage("No PTK project found (.main.ptk.yml).", "PTK init");
    if (action === "PTK init") return initializeProject(folder);
  }
  async function initializeProject(folder) {
    trusted();
    folder = folder || vscode.workspace.workspaceFolders?.[0];
    if (!folder) { await vscode.window.showInformationMessage("Open a folder before running PTK init."); return; }
    const configDir = await vscode.window.showInputBox({ title: "PTK init", prompt: "Configuration folder relative to the repository root", value: "config/ptk" });
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
        .flatMap(t => {
          const variants = t.project ? variantsFor(t) : [];
          return (variants.length ? variants : [undefined]).map(variant => makeTask(t, { variant }));
        });
    },
    async resolveTask(task) {
      if (!vscode.workspace.isTrusted) return;
      await settled();
      const d = task.definition;
      const targets = d.kind === "builtin" ? core.availableBuiltins(records) : core.availableTargets(records);
      const target = targets.find(t => t.kind === d.kind && t.name === d.name && t.root === d.root);
      if (!target || d.report && !core.canOpenReport(target) || target.ci && target.kind === "workflow" && !d.preview && !d.help && !d.report) return;
      if (!d.report && !d.help && !(d.kind === "job" && d.clean === true) && (target.spec.params || []).some(p => p.required && !p.env && !Object.hasOwn(d.kind === "builtin" ? d.inputs || {} : d.params || {}, p.name))) {
        const action = d.kind === "builtin" ? "Run Command with Options" : "Run Job or Workflow with Options";
        output.appendLine(`Use Project Toolkit: ${action} to supply required parameters for ${target.name}.`);
        return;
      }
      const resolved = makeTask(target, {
        variant: target.project && !d.help ? d.variant || core.selectedVariant(target.project) : undefined,
        preview: d.preview, params: d.params, runOptions: d.runOptions, help: d.help, inputs: d.inputs, clean: d.clean, reRun: d.reRun, report: d.report,
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
