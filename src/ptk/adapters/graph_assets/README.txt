PTK offline graph assets

Layout engine: @dagrejs/dagre 3.1.3 (includes @dagrejs/graphlib 4.0.6)
Upstream: https://github.com/dagrejs/dagre
API documentation: https://github.com/dagrejs/dagre/wiki
Package: https://registry.npmjs.org/@dagrejs/dagre/-/dagre-3.1.3.tgz
Upstream dist/dagre.min.js SHA-256:
54a503e346f93ca0bb10abe7999587e037262935687aca45eb4e4b0f64bbb578
License: MIT. dagre.LICENSE.txt and dagre.min.js.LEGAL.txt are copied verbatim.

The browser bundle is copied from the pinned npm package. Its trailing
sourceMappingURL line is removed because generated HTML must not request an
external source map. There are no other local changes to the engine. The
LEGAL notice is embedded in every generated HTML document with the engine.

To update: npm pack the exact chosen version with --ignore-scripts; extract
package/dist/dagre.min.js, package/LICENSE and
package/dist/dagre.min.js.LEGAL.txt; remove the sourceMappingURL line; update
this record and run graph-ui.test.js, Python graph/report tests and package tests.
No npm dependency resolution occurs when producing or opening PTK reports.

graph.js and graph.css are PTK's viewer, shared by standalone graph previews,
job reports and workflow reports. Graph text is inserted with textContent and
serialized JSON escapes HTML delimiters. No external assets are referenced.
