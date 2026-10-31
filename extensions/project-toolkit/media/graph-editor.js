/* global dagre, PtkDependencies */
"use strict";
window.PtkGraphEditor = (() => {
  function mount(container, context, { navigate, connect, locked, create, view = {}, refresh = () => {} }) {
    const D = PtkDependencies;
    const html = (tag, text, attrs = {}) => {
      const node = document.createElement(tag);
      if (text !== undefined) node.textContent = text;
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      return node;
    };
    const svgEl = (tag, attrs = {}, text) => {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const button = (text, action, label = text) => {
      const node = html("button", text, { type: "button", class: "secondary", "aria-label": label });
      node.addEventListener("click", action); return node;
    };
    const root = html("section", undefined, { class: "dependency-editor", "data-entity": context.kind, "aria-label": "Dependency graph" });
    root.dataset.expanded = String(!!view.expanded);
    container.append(root);
    const toolbar = html("div", undefined, { class: "dependency-toolbar" });
    const select = html("select", undefined, { id: "graph-selection", "aria-label": `Select ${context.kind}` });
    select.append(html("option", `Select a ${context.kind}…`, { value: "" }));
    let entries = [], error;
    try {
      entries = D.nodes(context.value); D.validate(entries);
      if (context.kind === "job") D.validateTargets(context.value, context.owner);
    } catch (issue) { error = issue.message; }
    for (const id of Object.keys(context.value || {})) {
      const node = entries.find(node => node.id === id);
      select.append(html("option", node?.label && node.label !== id ? `${id} · ${node.label}` : id, { value: id }));
    }
    select.value = context.selected || "";
    select.addEventListener("change", () => navigate(select.value ? [...context.path, select.value] : context.path));
    toolbar.append(html("label", `Select ${context.kind}`, { for: "graph-selection" }), select);
    if (create) toolbar.append(button(context.kind === "step" ? "New step" : "New workflow job", () => create({})));
    root.append(toolbar, html("p", "Prerequisites → dependents. Drag an output connector onto another node, or select a node and choose Add prerequisite. Joins wait for every prerequisite. Enter opens a focused node.", { class: "help" }));
    const message = html("p", error || "", { class: "notice error", role: "alert" });
    message.hidden = !error; root.append(message);
    function issue(text) { message.textContent = text; message.hidden = !text; }
    function write(from, to, remove = false) {
      try {
        if (locked(to)) throw new Error("These dependencies are locked. Use Raw YAML to edit them.");
        D.update(context.value, from, to, remove);
        connect(from, to, remove); issue("");
      } catch (error) { issue(error.message); }
    }
    const selected = entries.find(node => node.id === context.selected);
    if (selected) {
      const detail = D.describe(context.value[selected.id]);
      const summary = html("div", undefined, { class: "dependency-detail" });
      summary.append(html("strong", `${selected.id} · ${detail.label}`), html("code", detail.command));
      const dependents = entries.filter(node => node.needs.includes(selected.id));
      const links = html("div", undefined, { class: "row" });
      links.append(html("span", dependents.length ? "Used by:" : "No dependent nodes yet", { class: "muted" }));
      dependents.forEach(node => links.append(button(node.id, () => navigate([...context.path, node.id]), `Open dependent ${node.id}`)));
      if (create) links.append(button("New dependent", () => create({ needs: [selected.id] })));
      summary.append(links); root.append(summary);
      const controls = html("div", undefined, { class: "dependency-needs" });
      controls.append(html("strong", `${selected.id} needs`));
      if (!selected.needs.length) controls.append(html("span", "No prerequisites", { class: "muted" }));
      for (const from of selected.needs) {
        const remove = button(`${from} ×`, () => write(from, selected.id, true), `Remove prerequisite ${from} from ${selected.id}`);
        remove.disabled = locked(selected.id); controls.append(remove);
      }
      const choices = html("select", undefined, { id: "graph-prerequisite", "aria-label": "Add prerequisite" });
      choices.append(html("option", "Choose prerequisite…", { value: "" }));
      for (const from of entries) {
        try { D.update(context.value, from.id, selected.id); }
        catch { continue; }
        choices.append(html("option", from.id, { value: from.id }));
      }
      const add = button("Connect", () => write(choices.value, selected.id));
      add.disabled = true; choices.disabled = locked(selected.id) || choices.options.length === 1;
      choices.addEventListener("change", () => { add.disabled = !choices.value || locked(selected.id); });
      controls.append(choices, add); root.append(controls);
    }
    if (error) return () => {};
    if (!entries.length) { root.append(html("p", `No ${context.kind}s yet. Start with New ${context.kind === "step" ? "step" : "workflow job"}.`, { class: "empty" })); return () => {}; }
    root.append(html("p", `${entries.length} ${context.kind}s · ${entries.reduce((sum, node) => sum + node.needs.length, 0)} connections · ${entries.filter(node => !node.needs.length).length} roots. Independent branches may run in parallel.`, { class: "help" }));
    const controls = html("div", undefined, { class: "dependency-tools" });
    const search = html("input", undefined, { type: "search", id: "graph-search", "aria-label": "Find graph nodes", placeholder: "Find a name, command or job…" });
    search.value = view.search || "";
    const matches = html("output", "", { "aria-label": "Graph search matches", "aria-live": "polite" });
    const direction = html("select", undefined, { id: "graph-direction", "aria-label": "Graph direction" });
    direction.append(html("option", "Top to bottom", { value: "TB" }), html("option", "Left to right", { value: "LR" }));
    direction.value = view.direction || "TB";
    direction.addEventListener("change", () => { view.direction = direction.value; view.fitting = true; refresh(); });
    const highlight = html("input", undefined, { type: "checkbox" }); highlight.checked = view.highlight !== false;
    const highlightLabel = html("label", undefined, { class: "check" }); highlightLabel.append(highlight, document.createTextNode("Highlight related nodes"));
    root.dataset.highlight = String(highlight.checked && !!selected);
    highlight.addEventListener("change", () => { view.highlight = highlight.checked; root.dataset.highlight = String(highlight.checked && !!selected); });
    controls.append(search, matches, direction, highlightLabel);
    root.append(controls);
    const viewport = html("div", undefined, { class: "dependency-viewport", tabindex: "0", "aria-label": "Dependency canvas; scroll to pan" });
    const svg = svgEl("svg", { role: "group", "aria-label": "Prerequisites to dependents" });
    viewport.append(svg); root.append(viewport);
    const horizontal = view.direction === "LR";
    const graph = new dagre.graphlib.Graph().setGraph({ rankdir: horizontal ? "LR" : "TB", nodesep: 36, ranksep: 65, marginx: 30, marginy: 30 }).setDefaultEdgeLabel(() => ({}));
    const measure = document.createElement("canvas").getContext("2d");
    function wrap(text, font) {
      measure.font = font; const lines = []; let line = "";
      for (const char of text) {
        if (line && measure.measureText(line + char).width > 196) { lines.push(line); line = ""; }
        line += char;
      }
      if (line) lines.push(line); return lines;
    }
    for (const node of entries) {
      const lines = wrap(node.id, "600 14px system-ui");
      const detail = D.describe(context.value[node.id]);
      const subtitle = wrap([node.label && node.label !== node.id ? node.label : "", detail.command].filter(Boolean).join(" · "), "12px system-ui");
      if (subtitle.length > 2) { subtitle.length = 2; subtitle[1] = subtitle[1].slice(0, -1) + "…"; }
      graph.setNode(node.id, { width: 224, height: 58 + lines.length * 19 + subtitle.length * 16, lines, subtitle, detail });
    }
    for (const node of entries) for (const need of node.needs) graph.setEdge(need, node.id);
    dagre.layout(graph);
    const { width, height } = graph.graph();
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const defs = svgEl("defs"), marker = svgEl("marker", { id: "editor-graph-arrow", markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto", markerUnits: "userSpaceOnUse" });
    marker.append(svgEl("path", { d: "M0 0 L8 4 L0 8z" })); defs.append(marker); svg.append(defs);
    const family = D.related(entries, context.selected);
    for (const edge of graph.edges()) {
      svg.append(svgEl("path", {
        d: graph.edge(edge).points.map((point, i) => `${i ? "L" : "M"}${point.x},${point.y}`).join(" "),
        class: "dependency-edge", "data-from": edge.v, "data-to": edge.w,
        "data-active": String([edge.v, edge.w].includes(context.selected)), "marker-end": "url(#editor-graph-arrow)",
        "data-related": String([edge.v, edge.w].every(id => id === context.selected || family.ancestors.has(id) || family.descendants.has(id))),
      }));
    }
    for (const node of entries) {
      const box = graph.node(node.id);
      const group = svgEl("g", { class: "dependency-node", "data-kind": box.detail.kind, "data-node-id": node.id, "data-related": String(node.id === context.selected || family.ancestors.has(node.id) || family.descendants.has(node.id)), transform: `translate(${box.x - box.width / 2},${box.y - box.height / 2})` });
      const body = svgEl("g", { tabindex: "0", role: "button", "aria-label": `Edit ${context.kind} ${node.id}`, "aria-pressed": String(node.id === context.selected) });
      body.append(svgEl("rect", { width: box.width, height: box.height, rx: 8 }));
      body.append(svgEl("title", {}, `${node.id}\n${box.detail.label}: ${box.detail.command}\nNeeds: ${node.needs.join(", ") || "none"}`));
      let y = 24;
      for (const text of box.lines) { body.append(svgEl("text", { x: 14, y }, text)); y += 19; }
      body.append(svgEl("text", { x: 14, y, class: "dependency-kind" }, `${box.detail.label} · ${node.needs.length ? "needs " + node.needs.length : "root"}`)); y += 22;
      for (const text of box.subtitle) { body.append(svgEl("text", { x: 14, y, class: "dependency-subtitle" }, text)); y += 16; }
      body.addEventListener("click", () => navigate([...context.path, node.id]));
      body.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); navigate([...context.path, node.id]); } });
      group.append(body);
      group.append(svgEl("circle", { cx: horizontal ? 0 : box.width / 2, cy: horizontal ? box.height / 2 : 0, r: 6, class: "dependency-inlet" }));
      const port = svgEl("circle", { cx: horizontal ? box.width : box.width / 2, cy: horizontal ? box.height / 2 : box.height, r: 9, class: "dependency-outlet", "data-source": node.id });
      port.append(svgEl("title", {}, `Drag from ${node.id} to a dependent; or select the dependent and choose Add prerequisite.`));
      group.append(port); svg.append(group);
    }
    let scale = view.scale || 1, fitting = view.fitting !== false, disposed = false, drag;
    const output = html("output", "100%", { "aria-label": "Graph zoom" });
    function zoom(next) {
      const x = (viewport.scrollLeft + viewport.clientWidth / 2) / scale, y = (viewport.scrollTop + viewport.clientHeight / 2) / scale;
      scale = Math.max(.05, Math.min(3, next));
      view.scale = scale; view.fitting = fitting;
      svg.style.width = `${width * scale}px`; svg.style.height = `${height * scale}px`;
      output.value = `${Math.round(scale * 100)}%`;
      viewport.scrollLeft = x * scale - viewport.clientWidth / 2; viewport.scrollTop = y * scale - viewport.clientHeight / 2;
    }
    function fit() { if (disposed) return; fitting = true; zoom(Math.min(1, (viewport.clientWidth - 8) / width, (viewport.clientHeight - 8) / height)); viewport.scrollLeft = 0; viewport.scrollTop = 0; }
    function center(id) {
      const box = graph.node(id); if (!box) return;
      fitting = false; zoom(Math.max(.7, scale));
      viewport.scrollLeft = box.x * scale - viewport.clientWidth / 2; viewport.scrollTop = box.y * scale - viewport.clientHeight / 2;
      root.querySelectorAll(".dependency-node").forEach(node => { if (node.dataset.nodeId === id) node.querySelector('[role="button"]').focus({ preventScroll: true }); });
    }
    const focus = button("Focus selected", () => center(context.selected)); focus.disabled = !selected;
    toolbar.append(button("−", () => { fitting = false; zoom(scale / 1.25); }, "Zoom out"), output, button("+", () => { fitting = false; zoom(scale * 1.25); }, "Zoom in"), button("Fit", fit), button("100%", () => { fitting = false; zoom(1); }, "Actual size"), focus);
    const expand = button(view.expanded ? "Compact canvas" : "Expand canvas", () => { view.expanded = !view.expanded; root.dataset.expanded = String(view.expanded); expand.textContent = view.expanded ? "Compact canvas" : "Expand canvas"; expand.setAttribute("aria-label", expand.textContent); }); toolbar.append(expand);
    let matching = [], matchIndex = -1;
    function find() {
      view.search = search.value; const query = search.value.trim().toLowerCase(); matchIndex = -1;
      matching = entries.filter(node => `${node.id} ${node.label} ${graph.node(node.id).detail.command}`.toLowerCase().includes(query)).map(node => node.id);
      matches.value = query ? `${matching.length} matches` : "";
      root.querySelectorAll(".dependency-node").forEach(node => { node.dataset.match = String(!query || matching.includes(node.dataset.nodeId)); });
    }
    function nextMatch() { if (matching.length) center(matching[matchIndex = (matchIndex + 1) % matching.length]); }
    search.addEventListener("input", find); search.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); nextMatch(); } else if (event.key === "Escape") { search.value = ""; find(); } });
    controls.append(button("Find next", nextMatch)); find();
    const preview = svgEl("path", { class: "dependency-preview", visibility: "hidden" }); svg.append(preview);
    function cancel() { drag = undefined; preview.setAttribute("visibility", "hidden"); }
    viewport.addEventListener("pointerdown", event => {
      const from = event.target.closest("[data-source]")?.dataset.source;
      if (event.button !== 0 || !from && event.target.closest(".dependency-node")) return;
      if (!from && event.pointerType === "touch") return;
      drag = { from, x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
      if (!from) { fitting = false; view.fitting = false; }
      viewport.setPointerCapture(event.pointerId); event.preventDefault();
      if (from) preview.setAttribute("visibility", "visible");
    });
    viewport.addEventListener("pointermove", event => {
      if (!drag) return;
      if (!drag.from) { viewport.scrollLeft = drag.left + drag.x - event.clientX; viewport.scrollTop = drag.top + drag.y - event.clientY; return; }
      const source = graph.node(drag.from), point = svg.createSVGPoint();
      point.x = event.clientX; point.y = event.clientY;
      const end = point.matrixTransform(svg.getScreenCTM().inverse());
      preview.setAttribute("d", `M${source.x + (horizontal ? source.width / 2 : 0)},${source.y + (horizontal ? 0 : source.height / 2)} L${end.x},${end.y}`);
    });
    viewport.addEventListener("pointerup", event => {
      const from = drag?.from;
      const to = document.elementFromPoint(event.clientX, event.clientY)?.closest(".dependency-node")?.dataset.nodeId;
      cancel();
      if (from && to) { event.preventDefault(); write(from, to); }
    });
    viewport.addEventListener("pointercancel", cancel);
    viewport.addEventListener("lostpointercapture", cancel);
    viewport.addEventListener("keydown", event => {
      if (event.key === "Escape") cancel();
      else if (!event.ctrlKey && !event.metaKey && !event.altKey && ["+", "=", "-", "0", "f"].includes(event.key.toLowerCase())) {
        event.preventDefault();
        if (event.key === "0") fit(); else if (event.key.toLowerCase() === "f") center(context.selected);
        else { fitting = false; zoom(scale * (event.key === "-" ? .8 : 1.25)); }
      }
    });
    viewport.addEventListener("wheel", event => { if (event.ctrlKey || event.metaKey) { event.preventDefault(); fitting = false; zoom(scale * (event.deltaY > 0 ? .9 : 1.1)); } }, { passive: false });
    viewport.addEventListener("scroll", () => { view.left = viewport.scrollLeft; view.top = viewport.scrollTop; if (view.left || view.top) { fitting = false; view.fitting = false; } });
    root.append(html("p", "Canvas shortcuts: + / − zoom, 0 fits all, F focuses selection, Escape cancels a connection. Ctrl/Cmd + wheel zooms. Search dims unmatched nodes without hiding dependencies.", { class: "help" }));
    const observer = new ResizeObserver(() => { if (fitting) fit(); }); observer.observe(viewport);
    requestAnimationFrame(() => { if (disposed) return; if (fitting) fit(); else { const left = view.left || 0, top = view.top || 0; zoom(scale); viewport.scrollLeft = left; viewport.scrollTop = top; } });
    return () => { view.left = viewport.scrollLeft; view.top = viewport.scrollTop; disposed = true; cancel(); observer.disconnect(); };
  }
  return { mount };
})();
