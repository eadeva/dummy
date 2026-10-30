/* PTK dependency viewer. All graph text is data, never HTML. */
(() => {
  "use strict";
  const svgNS = "http://www.w3.org/2000/svg";
  const element = (name, attrs = {}, text) => {
    const node = document.createElementNS(svgNS, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const html = (name, text) => {
    const node = document.createElement(name);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const stateOf = node => node.status || (node.selected === false ? "unselected" : node.selected ? "selected" : "configured");
  const stateLabel = node => {
    const state = stateOf(node);
    return ({ hidden: "Details hidden", unselected: "Not selected" }[state] || state[0].toUpperCase() + state.slice(1)) + (node.allowed_failure ? " · failure allowed" : "");
  };
  document.querySelectorAll("details.ptk-graph").forEach((root, instance) => {
    const data = JSON.parse(root.querySelector(".ptk-graph-data").textContent);
    const byId = new Map(data.nodes.map(node => [node.id, node]));
    const viewport = root.querySelector(".ptk-graph-viewport");
    const svg = root.querySelector("svg");
    const inspector = root.querySelector(".ptk-graph-inspector");
    const output = root.querySelector("output");
    const graph = new dagre.graphlib.Graph().setGraph({ rankdir: "TB", nodesep: 34, ranksep: 54, marginx: 24, marginy: 24 }).setDefaultEdgeLabel(() => ({}));
    const rendered = new Map();
    let initialized = false, scale = 1, fitting = true, width = 1, height = 1;
    const zoom = (next, centered = true) => {
      const cx = (viewport.scrollLeft + viewport.clientWidth / 2) / scale;
      const cy = (viewport.scrollTop + viewport.clientHeight / 2) / scale;
      scale = Math.max(0.02, Math.min(3, next));
      svg.style.width = `${width * scale}px`; svg.style.height = `${height * scale}px`;
      output.value = `${Math.round(scale * 100)}%`;
      if (centered) { viewport.scrollLeft = cx * scale - viewport.clientWidth / 2; viewport.scrollTop = cy * scale - viewport.clientHeight / 2; }
    };
    const fit = () => { fitting = true; zoom(Math.min(1, (viewport.clientWidth - 8) / width, (viewport.clientHeight - 8) / height), false); viewport.scrollLeft = 0; viewport.scrollTop = 0; };
    function select(id, reveal = false) {
      const node = byId.get(id);
      for (const [key, group] of rendered) group.setAttribute("aria-pressed", String(key === id));
      for (const edge of svg.querySelectorAll(".ptk-graph-edge")) edge.dataset.active = String(edge.dataset.from === id || edge.dataset.to === id);
      inspector.replaceChildren(html("h3", id));
      const fields = html("dl"); inspector.append(fields);
      const field = (label, value) => { fields.append(html("dt", label), html("dd", value)); };
      const links = (label, ids) => {
        fields.append(html("dt", label)); const value = html("dd"); fields.append(value);
        if (!ids.length) value.textContent = "None";
        for (const target of ids) { const button = html("button", target); button.type = "button"; button.addEventListener("click", () => select(target, true)); value.append(button); }
      };
      field("State", stateLabel(node));
      if (node.label) field("Target", node.label);
      if (node.variant) field("Variant", node.variant);
      if (node.duration !== undefined) field("Duration", `${node.duration.toFixed(2)}s`);
      links("Needs", node.needs);
      links("Used by", data.nodes.filter(other => other.needs.includes(id)).map(other => other.id));
      if (node.message) field("Message", node.message);
      if (reveal) {
        fitting = false; zoom(Math.max(scale, 0.8), false);
        const position = graph.node(id);
        viewport.scrollLeft = position.x * scale - viewport.clientWidth / 2;
        viewport.scrollTop = position.y * scale - viewport.clientHeight / 2;
        rendered.get(id).focus({ preventScroll: true });
      }
    }
    function initialize() {
      if (initialized || !root.open) return;
      initialized = true;
      if (!data.nodes.length) {
        viewport.replaceChildren(html("p", "No dependencies recorded."));
        root.querySelector(".ptk-graph-toolbar").hidden = true;
        inspector.hidden = true; return;
      }
      const measure = document.createElement("canvas").getContext("2d");
      const wrap = (text, font) => {
        measure.font = font; const lines = []; let line = "";
        for (const char of text) {
          if (line && measure.measureText(line + char).width > 216) { lines.push(line); line = ""; }
          line += char;
        }
        if (line) lines.push(line);
        return lines;
      };
      for (const node of data.nodes) {
        const lines = wrap(node.id, "600 14px system-ui");
        const subtitle = node.label ? wrap(node.label, "12px system-ui") : [];
        graph.setNode(node.id, { width: 246, height: 42 + lines.length * 18 + subtitle.length * 16, lines, subtitle });
      }
      for (const node of data.nodes) for (const need of node.needs) graph.setEdge(node.id, need);
      dagre.layout(graph);
      ({ width, height } = graph.graph());
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const markerId = `ptk-graph-arrow-${instance}`;
      const defs = element("defs"), marker = element("marker", { id: markerId, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto", markerUnits: "userSpaceOnUse" });
      marker.append(element("path", { d: "M0 0 L8 4 L0 8z", class: "ptk-graph-arrow" })); defs.append(marker); svg.append(defs);
      for (const edge of graph.edges()) {
        const points = graph.edge(edge).points;
        const d = points.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" ");
        svg.append(element("path", { d, class: "ptk-graph-edge", "data-from": edge.v, "data-to": edge.w, "marker-end": `url(#${markerId})`, "stroke-linejoin": "round" }));
      }
      for (const node of data.nodes) {
        const box = graph.node(node.id), x = box.x - box.width / 2, y = box.y - box.height / 2;
        const group = element("g", { class: "ptk-graph-node", transform: `translate(${x},${y})`, "data-node-id": node.id, "data-status": stateOf(node), "data-allowed": String(!!node.allowed_failure), tabindex: 0, role: "button", "aria-label": `${node.id}: ${stateLabel(node)}`, "aria-pressed": "false" });
        group.append(element("title", {}, `${node.id}\n${stateLabel(node)}\nNeeds: ${node.needs.join(", ") || "none"}`));
        group.append(element("rect", { width: box.width, height: box.height, rx: 9 }));
        let lineY = 24;
        for (const text of box.lines) { group.append(element("text", { x: 15, y: lineY }, text)); lineY += 18; }
        for (const text of box.subtitle) { group.append(element("text", { x: 15, y: lineY, class: "ptk-graph-subtitle" }, text)); lineY += 16; }
        group.append(element("text", { x: 15, y: box.height - 13, class: "ptk-graph-state" }, stateLabel(node)));
        group.addEventListener("click", () => select(node.id));
        group.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(node.id); } });
        svg.append(group); rendered.set(node.id, group);
      }
      fit();
    }
    root.addEventListener("toggle", () => { initialize(); if (root.open && fitting && data.nodes.length) fit(); });
    root.querySelectorAll("[data-graph-action]").forEach(button => button.addEventListener("click", () => {
      if (button.dataset.graphAction === "fit") fit();
      else { fitting = false; zoom(scale * (button.dataset.graphAction === "in" ? 1.3 : 1 / 1.3)); }
    }));
    let drag;
    viewport.addEventListener("pointerdown", event => {
      if (event.pointerType === "touch" || event.button !== 0 || event.target.closest(".ptk-graph-node")) return;
      drag = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
      viewport.setPointerCapture(event.pointerId); event.preventDefault();
    });
    viewport.addEventListener("pointermove", event => { if (drag) { viewport.scrollLeft = drag.left + drag.x - event.clientX; viewport.scrollTop = drag.top + drag.y - event.clientY; } });
    viewport.addEventListener("lostpointercapture", () => { drag = undefined; });
    new ResizeObserver(() => { if (initialized && root.open && fitting && data.nodes.length) fit(); }).observe(viewport);
    initialize();
  });
})();
