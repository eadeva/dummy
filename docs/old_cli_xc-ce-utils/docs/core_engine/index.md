# Core Engine Architecture Documentation (arc42)

This is the arc42-structured architecture documentation for `xc_ce_utils.core_engine` —
the configuration-driven, multi-variant execution orchestrator at the heart of XC-CE Utils.

## Chapters

1. [Introduction and Goals](01_introduction_and_goals.md)
2. [Architecture Constraints](02_architecture_constraints.md)
3. [System Scope and Context](03_system_scope_and_context.md)
4. [Solution Strategy](04_solution_strategy.md)
5. [Building Block View](05_building_block_view.md)
6. [Runtime View](06_runtime_view.md)
7. [Deployment View](07_deployment_view.md)
8. [Crosscutting Concepts](08_crosscutting_concepts.md)
9. [Architecture Decisions](09_architecture_decisions.md)
10. [Quality Requirements](10_quality_requirements.md)
11. [Risks and Technical Debt](11_risks_and_technical_debt.md)
12. [Glossary](12_glossary.md)

## Reference / Deep-Dive Appendix

Detailed, mechanical reference material (full API surfaces, per-step-type parameter tables,
Pydantic schema field lists) lives under `reference/` rather than in the arc42 chapters
themselves, which stay focused on architecture rationale and structure:

- [Step Reference](reference/step_reference.md) — `StepRegistry` mechanism and the full
  catalog of 100+ step types, split into category pages under `reference/steps/`.
- [Variant Matrix](reference/variant_matrix.md) — `VariantMatrix` / `Variant` API reference.
- [Wrappers](reference/wrappers.md) — build tool wrapper API reference (Conan, CMake, Bazel,
  Make, scripts, ccache).
- [Environment Setup](reference/environment_setup.md) — legacy setup mixins (thin shims).
- [Environment Setup Flow](reference/environment_setup_flow.md) — **authoritative** boot
  sequence, `SetupPhase` chain, environment isolation, diagnostics.
- [Configuration Schema Reference](reference/config_schema_reference.md) — Pydantic v2 models
  for every YAML key.
