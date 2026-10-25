---
name: ptk-development
description: Modify ptk core code, adapters, use cases or extension interfaces.
---

# ptk-development

1. Read `docs/development.rst`, `docs/PLAN.md` and the relevant tests before changing code.

2. Keep dependencies inward: drivers -> application -> domain; adapters implement ports; wire concrete implementations in bootstrap.

3. Keep domain logic pure. Use fakes for use cases and real temporary processes/files for adapter tests.

4. Distinguish implemented behavior from roadmap promises; inspect registered built-ins and commands before documenting them.

5. Fix the smallest coherent problem and cover the observable failure rather than duplicating implementation in tests.

6. Run `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and the Sphinx warning-as-error build.

7. Exercise Windows-specific paths in Windows CI; do not claim cross-platform success from Linux alone.

8. Update docs, examples and relevant authoring skills with behavior changes. Keep secrets and generated workspace outputs out of git.

9. Review CI results before marking a milestone complete; record explicit remaining limitations in PLAN.md.

10. Extension contracts and explicit distribution loading are documented in `docs/plugins.rst`; test third-party entry points without importing unselected distributions.
