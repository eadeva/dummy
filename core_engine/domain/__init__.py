"""Domain layer for core_engine.

Foundational, dependency-free modules (exceptions, runtime context,
variant matrix, registries, comparison, env access, layered config
primitives) that the rest of core_engine builds on. Modules in this
package must not import from ``application``, ``adapters``, or ``cli``.
"""
