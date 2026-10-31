/* Offline DAG viewer. Workflow jobs contain independent, recorded step DAGs. */
(() => {
  "use strict";
  const svgNS = "http://www.w3.org/2000/svg";
  const element = (name, attrs = {}, text) => {
    const node = document.createElementNS(svgNS, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const html = (name, text) => { const node = document.createElement(name); if (text !== undefined) node.textContent = text; return node; };
  const stateOf = node => node.status || (node.selected === false ? "unselected" : node.selected ? "selected" : "configured");
  const stateLabel = node => {
    const state = stateOf(node);
    return ({ hidden: "Details hidden", unselected: "Not selected", not_run: "Not run" }[state] || state[0].toUpperCase() + state.slice(1)) + (node.allowed_failure ? " · failure allowed" : "");
  };
  document.querySelectorAll("details.ptk-graph").forEach((root, instance) => {
    const data = JSON.parse(root.querySelector(".ptk-graph-data").textContent);
    const byId = new Map(), expanded = new Set(), rendered = new Map(), positions = new Map(), toggles = new Map();
    const childKey = (parent, id) => `@${JSON.stringify([parent, id])}`;
    for (const node of data.nodes) {
      byId.set(node.id, { ...node, key: node.id, parent: null });
      for (const child of node.children?.nodes || []) byId.set(childKey(node.id, child.id), { ...child, key: childKey(node.id, child.id), parent: node.id });
    }
    const viewport = root.querySelector(".ptk-graph-viewport"), svg = root.querySelector("svg");
    const inspector = root.querySelector(".ptk-graph-inspector"), output = root.querySelector("output");
    let initialized = false, scale = 1, fitting = true, width = 1, height = 1, selected;
    const zoom = (next, centered = true) => {
      const cx = (viewport.scrollLeft + viewport.clientWidth / 2) / scale, cy = (viewport.scrollTop + viewport.clientHeight / 2) / scale;
      scale = Math.max(0.02, Math.min(3, next));
      svg.style.width = `${width * scale}px`; svg.style.height = `${height * scale}px`; output.value = `${Math.round(scale * 100)}%`;
      if (centered) { viewport.scrollLeft = cx * scale - viewport.clientWidth / 2; viewport.scrollTop = cy * scale - viewport.clientHeight / 2; }
    };
    const fit = () => { fitting = true; zoom(Math.min(1, (viewport.clientWidth - 8) / width, (viewport.clientHeight - 8) / height), false); viewport.scrollLeft = 0; viewport.scrollTop = 0; };
    const localKey = (node, id) => node.parent === null ? id : childKey(node.parent, id);
    function select(key, reveal = false) {
      const node = byId.get(key); if (!node) return;
      if (node.parent !== null && !expanded.has(node.parent)) { expanded.add(node.parent); draw(); }
      selected = key;
      for (const [id, group] of rendered) group.setAttribute("aria-pressed", String(id === key));
      for (const edge of svg.querySelectorAll(".ptk-graph-edge")) edge.dataset.active = String(edge.dataset.from === key || edge.dataset.to === key);
      inspector.replaceChildren(html("h3", node.parent === null ? node.id : `${node.parent} / ${node.id}`));
      const fields = html("dl"); inspector.append(fields);
      const field = (label, value) => fields.append(html("dt", label), html("dd", value));
      const links = (label, ids) => {
        fields.append(html("dt", label)); const value = html("dd"); fields.append(value);
        if (!ids.length) value.textContent = "None";
        for (const id of ids) { const button = html("button", id); button.type = "button"; button.addEventListener("click", () => select(localKey(node, id), true)); value.append(button); }
      };
      field("State", stateLabel(node));
      if (node.parent !== null) field("Job", byId.get(node.parent).label || node.parent);
      if (node.label) field(node.kind === "bazel-target" ? "Rule kind" : node.kind === "gn-target" ? "Target type" : "Target", node.label);
      if (node.variant) field("Variant", node.variant);
      if (node.configuration) field("Bazel configuration", node.configuration);
      if (node.toolchain) field("Toolchain", node.toolchain);
      if (node.duration !== undefined) field("Duration", ["skipped", "not_run", "hidden", "reused"].includes(node.status) ? "Not executed" : `${node.duration.toFixed(2)}s`);
      links("Needs", node.needs);
      const peers = node.parent === null ? data.nodes : byId.get(node.parent).children.nodes;
      links("Used by", peers.filter(other => other.needs.includes(node.id)).map(other => other.id));
      if (node.message) field("Message", node.message);
      if (node.children?.nodes.length) {
        const button = html("button", expanded.has(key) ? "Collapse steps" : `Expand ${node.children.nodes.length} steps`);
        button.type = "button"; button.setAttribute("aria-expanded", String(expanded.has(key))); button.addEventListener("click", () => toggle(key)); inspector.append(button);
      }
      if (node.target) {
        const link = html("a", "Open execution details"); link.href = `#${node.target}`; inspector.append(link);
        document.dispatchEvent(new CustomEvent("ptk:select", { detail: { target: node.target } }));
      }
      if (reveal) {
        fitting = false; zoom(Math.max(scale, 0.8), false);
        const position = positions.get(key);
        viewport.scrollLeft = position.x * scale - viewport.clientWidth / 2; viewport.scrollTop = position.y * scale - viewport.clientHeight / 2;
        rendered.get(key)?.focus({ preventScroll: true });
      }
    }
    const measure = document.createElement("canvas").getContext("2d");
    const wrap = (text, font) => {
      measure.font = font; const lines = []; let line = "";
      for (const char of text) { if (line && measure.measureText(line + char).width > 216) { lines.push(line); line = ""; } line += char; }
      if (line) lines.push(line); return lines;
    };
    function box(node) {
      const lines = wrap(node.id, "600 14px system-ui"), subtitle = node.label && node.label !== node.id ? wrap(node.label, "12px system-ui") : [];
      const expandable = !!node.children?.nodes.length;
      return { width: 246, height: 42 + lines.length * 18 + subtitle.length * 16 + (expandable ? 36 : 0), lines, subtitle, expandable };
    }
    const layout = () => new dagre.graphlib.Graph().setGraph({ rankdir: "TB", nodesep: 34, ranksep: 54, marginx: 24, marginy: 24 }).setDefaultEdgeLabel(() => ({}));
    const markerId = `ptk-graph-arrow-${instance}`;
    function edges(graph, parent, dx = 0, dy = 0) {
      for (const edge of graph.edges()) {
        const d = graph.edge(edge).points.map((point, index) => `${index ? "L" : "M"}${point.x + dx},${point.y + dy}`).join(" ");
        svg.append(element("path", { d, class: `ptk-graph-edge${parent === null ? "" : " ptk-graph-internal-edge"}`, "data-from": parent === null ? edge.v : childKey(parent, edge.v), "data-to": parent === null ? edge.w : childKey(parent, edge.w), "marker-end": `url(#${markerId})`, "stroke-linejoin": "round" }));
      }
    }
    function drawNode(node, size, x, y) {
      const group = element("g", { class: "ptk-graph-node", transform: `translate(${x},${y})`, "data-node-id": node.key, "data-kind": node.kind || "", "data-status": stateOf(node), "data-allowed": String(!!node.allowed_failure), tabindex: 0, role: "button", "aria-label": `${node.parent === null ? "" : node.parent + " / "}${node.id}: ${stateLabel(node)}`, "aria-pressed": "false" });
      group.append(element("title", {}, `${node.id}\n${stateLabel(node)}\nNeeds: ${node.needs.join(", ") || "none"}`));
      group.append(element("rect", { width: size.width, height: size.height - (size.expandable ? 36 : 0), rx: 9 }));
      let lineY = 24;
      for (const text of size.lines) { group.append(element("text", { x: 15, y: lineY, class: "ptk-graph-title" }, text)); lineY += 18; }
      for (const text of size.subtitle) { group.append(element("text", { x: 15, y: lineY, class: "ptk-graph-subtitle" }, text)); lineY += 16; }
      group.append(element("text", { x: 15, y: size.height - (size.expandable ? 36 : 0) - 13, class: "ptk-graph-state" }, stateLabel(node)));
      group.addEventListener("click", () => select(node.key));
      group.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(node.key); } });
      svg.append(group); rendered.set(node.key, group); positions.set(node.key, { x: x + size.width / 2, y: y + size.height / 2 });
      if (size.expandable) {
        const button = element("g", { class: "ptk-graph-toggle", transform: `translate(${x},${y + size.height - 32})`, tabindex: 0, role: "button", "aria-label": `${expanded.has(node.key) ? "Collapse" : "Expand"} steps of ${node.id}`, "aria-expanded": String(expanded.has(node.key)), "data-job-id": node.key });
        button.append(element("rect", { width: size.width, height: 28, rx: 5 }));
        button.append(element("text", { x: 15, y: 19 }, `${expanded.has(node.key) ? "− Hide" : "+ Show"} ${node.children.nodes.length} steps`));
        button.addEventListener("click", () => toggle(node.key)); button.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); toggle(node.key); } });
        svg.append(button); toggles.set(node.key, button);
      }
    }
    function draw() {
      svg.replaceChildren(); rendered.clear(); positions.clear(); toggles.clear();
      const outer = layout(), nested = new Map();
      for (const node of data.nodes) {
        const size = box(node); size.headerHeight = size.height;
        if (expanded.has(node.id) && node.children?.nodes.length) {
          const inner = layout();
          for (const child of node.children.nodes) inner.setNode(child.id, box(child));
          for (const child of node.children.nodes) for (const need of child.needs) if (inner.hasNode(need)) inner.setEdge(need, child.id);
          dagre.layout(inner); nested.set(node.id, inner);
          size.width = Math.max(size.width, inner.graph().width + 24); size.height += inner.graph().height + 16;
        }
        outer.setNode(node.id, size);
      }
      for (const node of data.nodes) for (const need of node.needs) if (outer.hasNode(need)) outer.setEdge(need, node.id);
      dagre.layout(outer); ({ width, height } = outer.graph());
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const defs = element("defs"), marker = element("marker", { id: markerId, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto", markerUnits: "userSpaceOnUse" });
      marker.append(element("path", { d: "M0 0 L8 4 L0 8z", class: "ptk-graph-arrow" })); defs.append(marker); svg.append(defs);
      edges(outer, null);
      for (const raw of data.nodes) {
        const node = byId.get(raw.id), size = outer.node(raw.id), x = size.x - size.width / 2, y = size.y - size.height / 2;
        const inner = nested.get(raw.id);
        if (inner) svg.append(element("rect", { class: "ptk-graph-container", "data-container-id": node.id, x, y, width: size.width, height: size.height, rx: 12 }));
        drawNode(node, { ...size, height: size.headerHeight }, x, y);
        if (inner) {
          const dx = x + 12, dy = y + size.headerHeight;
          edges(inner, node.id, dx, dy);
          for (const child of raw.children.nodes) { const childBox = inner.node(child.id); drawNode(byId.get(childKey(node.id, child.id)), childBox, dx + childBox.x - childBox.width / 2, dy + childBox.y - childBox.height / 2); }
        }
      }
      fit();
    }
    function toggle(key) {
      if (expanded.has(key)) { expanded.delete(key); if (byId.get(selected)?.parent === key) selected = key; } else expanded.add(key);
      draw(); select(selected || key); toggles.get(key)?.focus({ preventScroll: true });
    }
    function initialize() {
      if (initialized || !root.open) return;
      initialized = true;
      if (!data.nodes.length) { viewport.replaceChildren(html("p", "No dependencies recorded.")); root.querySelector(".ptk-graph-toolbar").hidden = true; inspector.hidden = true; return; }
      draw();
    }
    root.addEventListener("toggle", () => { initialize(); if (root.open && fitting && data.nodes.length) fit(); });
    root.querySelectorAll("[data-graph-action]").forEach(button => button.addEventListener("click", () => {
      const action = button.dataset.graphAction;
      if (action === "fit") fit();
      else if (action === "expand" || action === "collapse") { expanded.clear(); if (action === "expand") for (const node of data.nodes) if (node.children?.nodes.length) expanded.add(node.id); if (action === "collapse" && byId.get(selected)?.parent !== null) selected = byId.get(selected)?.parent; draw(); if (selected) select(selected); }
      else { fitting = false; zoom(scale * (action === "in" ? 1.3 : 1 / 1.3)); }
    }));
    document.addEventListener("ptk:graph-select", event => {
      const node = [...byId.values()].find(node => node.target === event.detail.target); if (!node) return;
      root.open = true; initialize(); select(node.key, true);
    });
    let drag;
    viewport.addEventListener("pointerdown", event => {
      if (event.pointerType === "touch" || event.button !== 0 || event.target.closest(".ptk-graph-node,.ptk-graph-toggle")) return;
      drag = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop }; viewport.setPointerCapture(event.pointerId); event.preventDefault();
    });
    viewport.addEventListener("pointermove", event => { if (drag) { viewport.scrollLeft = drag.left + drag.x - event.clientX; viewport.scrollTop = drag.top + drag.y - event.clientY; } });
    viewport.addEventListener("lostpointercapture", () => { drag = undefined; });
    new ResizeObserver(() => { if (initialized && root.open && fitting && data.nodes.length) fit(); }).observe(viewport);
    initialize();
  });
})();
