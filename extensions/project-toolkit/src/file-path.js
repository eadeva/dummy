"use strict";

const fs = require("node:fs");
const path = require("node:path");

// Match PTK's resolved filesystem paths, including Windows short directory names.
// New entity files and {name} templates resolve through their existing ancestor.
function canonicalPath(file) {
  let current = path.resolve(file);
  const missing = [];
  for (;;) {
    try { return path.join(fs.realpathSync.native(current), ...missing); }
    catch (error) {
      if (error.code !== "ENOENT") throw error;
      const parent = path.dirname(current);
      if (parent === current) throw error;
      missing.unshift(path.basename(current));
      current = parent;
    }
  }
}

module.exports = { canonicalPath };
