/* Recorded data only: no network, script execution or configuration lookup. */
(() => {
  "use strict";
  const filters = new Map();
  document.querySelectorAll("[data-filter]").forEach(root => {
    const inputs = [...root.querySelectorAll(":scope > .filter-toolbar [name]")];
    const records = [...root.querySelectorAll(":scope > [data-record]")];
    const defaults = new Map(inputs.map(input => [input, input.value]));
    const apply = () => {
      let visible = 0, occurrences = 0;
      for (const record of records) {
        record.hidden = inputs.some(input => input.value && (input.name === "search" ? !(record.dataset.search ?? record.textContent).toLowerCase().includes(input.value.toLowerCase()) : record.dataset[input.name] !== input.value));
        if (!record.hidden) { visible++; occurrences += Number(record.dataset.count || 0); }
      }
      root.querySelector(":scope > [data-filter-count]").textContent = `${visible} of ${records.length} ${root.dataset.filter} shown` + (root.dataset.filter === "diagnostics" ? ` · ${occurrences} log occurrences in this selection` : "");
    };
    for (const input of inputs) { input.addEventListener("input", apply); input.addEventListener("change", apply); }
    root.querySelector("[data-reset]").addEventListener("click", () => { for (const input of inputs) input.value = defaults.get(input); apply(); });
    for (const button of root.querySelectorAll("[data-diagnostic-card]")) button.addEventListener("click", () => {
      for (const input of inputs) input.value = "";
      root.querySelector('[name="source"]').value = "log";
      const key = button.dataset.diagnosticCard;
      root.querySelector('[name="disposition"]').value = ["error", "warning"].includes(key) ? "active" : key;
      root.querySelector('[name="severity"]').value = ["error", "warning"].includes(key) ? key : "";
      apply();
    });
    filters.set(root, { inputs, apply }); apply();
  });
  function reveal(id, scroll = true) {
    const target = document.getElementById(id);
    if (!target) return;
    for (let node = target; node; node = node.parentElement) {
      if (node.tagName === "DETAILS") node.open = true;
      if (node.hasAttribute("data-record") && node.hidden) {
        const root = node.parentElement.closest("[data-filter]");
        const filter = filters.get(root);
        if (filter) { for (const input of filter.inputs) input.value = ""; filter.apply(); }
      }
    }
    if (target.classList.contains("execution-item")) {
      document.querySelectorAll(".execution-item.is-selected").forEach(item => item.classList.remove("is-selected"));
      target.classList.add("is-selected");
    }
    if (scroll) { target.scrollIntoView({ block: "start" }); const focus = target.querySelector("summary") || target; if (!focus.hasAttribute("tabindex")) focus.tabIndex = -1; focus.focus({ preventScroll: true }); }
  }
  document.addEventListener("click", event => {
    const anchor = event.target.closest('a[href^="#"]');
    if (anchor) { const id = anchor.getAttribute("href").slice(1); if (document.getElementById(id)) { event.preventDefault(); history.replaceState(null, "", `#${id}`); reveal(id); } }
    const graph = event.target.closest("[data-show-graph]");
    if (graph) { document.dispatchEvent(new CustomEvent("ptk:graph-select", { detail: { target: graph.dataset.showGraph } })); document.getElementById("graph").scrollIntoView({ block: "start" }); }
  });
  document.addEventListener("ptk:select", event => reveal(event.detail.target, false));
  addEventListener("hashchange", () => reveal(location.hash.slice(1)));
  if (location.hash) reveal(location.hash.slice(1));
  const nav = document.querySelector(".section-nav");
  if (nav) {
    const observer = new IntersectionObserver(entries => { for (const entry of entries) if (entry.isIntersecting) { for (const link of nav.querySelectorAll("a")) link.setAttribute("aria-current", String(link.hash === `#${entry.target.id}`)); } }, { rootMargin: "-70px 0px -65% 0px" });
    for (const link of nav.querySelectorAll("a")) observer.observe(document.getElementById(link.hash.slice(1)));
  }
})();
