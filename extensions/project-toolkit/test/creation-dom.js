"use strict";
// Small DOM boundary for setup state tests; real layout/focus is covered by Playwright.
class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attributes = {}; this.events = {}; this._value = undefined; this.disabled = false; this.textContent = ""; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, action) { (this.events[name] ||= []).push(action); }
  emit(name) { if (!this.disabled) for (const action of this.events[name] || []) action({ target: this }); }
  get value() { return this._value ?? (this.tagName === "SELECT" ? this.all().find(node => node.tagName === "OPTION")?.attributes.value : "") ?? ""; }
  set value(value) { this._value = value; }
  all() { return this.children.flatMap(child => child instanceof Element ? [child, ...child.all()] : []); }
  querySelectorAll(selector) {
    return this.all().filter(node => selector.split(",").some(part => {
      part = part.trim();
      const match = /^\[([^=]+)="([^"]*)"\]$/.exec(part);
      return match ? node.attributes[match[1]] === match[2] : node.tagName.toLowerCase() === part;
    }));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  focus() {}
}
function document() {
  return { createElement: tag => new Element(tag), createTextNode: text => text };
}
module.exports = { Element, document };
