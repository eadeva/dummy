---
name: ptk-docs-writing
description: Document ptk features, configuration or project jobs and maintain
  tested examples.
---

# ptk-docs-writing

Use this skill only in PTK's own source checkout. Confirm the checkout, project instructions and declared dependency groups first; do not impose PTK's development layout or test commands on consuming projects. For project-specific configuration, use [configuration authoring](../ptk-config-authoring/SKILL.md).

1. Read `docs/index.rst`, `docs/guides/configuration.rst` and the implementation for the feature.

2. Use reStructuredText for Sphinx pages and add new pages to the toctree.

3. Generate configuration field tables through the ptk-schema directive; use YAML paths, allowed values, defaults and constraints. Keep source-module maps, Python API signatures and autodoc/pydoc output out of the published docs. Do not copy field lists that can drift. Keep plugin implementation contracts in the plugin-development skill references.

4. Use literalinclude for runnable configuration and scripts; add tests that execute the same source examples.

5. Verify command names and options against `ptk COMMAND --help` before publishing instructions.

6. Clearly separate supported behavior from planned commands and plugin integrations.

7. For CLI requirements, follow `docs/requirements/index.rst`: retain IDs and traceability, distinguish lifecycle status from implementation evidence, and use QM/false/false classifications. Keep the meta-model and old CLI archive out of build inputs. Update the relevant arc42 chapter when behavior or boundaries change.

8. Build with `uv sync --group docs` then `uv run sphinx-build -W --keep-going -b html docs docs/_build/html`.

9. Run example tests and skill-catalog validation; inspect generated pages for missing tables and broken internal links.

10. Keep credentials fictional, use project-relative paths, and describe platform-specific requirements.

11. Update the relevant .claude/skills instructions when changing an authoring workflow.
