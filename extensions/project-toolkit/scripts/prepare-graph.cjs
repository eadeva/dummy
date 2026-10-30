"use strict";
// One pinned engine source serves reports and the VSIX, including its notices.
const fs = require("node:fs"), path = require("node:path");
const source = path.resolve(__dirname, "../../../src/ptk/adapters/graph_assets");
const target = path.resolve(__dirname, "../media/graph-engine");
fs.mkdirSync(target, { recursive: true });
for (const file of ["dagre.min.js", "dagre.LICENSE.txt", "dagre.min.js.LEGAL.txt", "README.txt"]) fs.copyFileSync(path.join(source, file), path.join(target, file));
