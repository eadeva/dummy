"""Lightweight registry mapping wrapper names to their import paths.

The wrapper registry is the central directory consulted by step classes
(via the upcoming ``WrappedStep`` base in Phase 2 #2) to resolve the
concrete wrapper implementation by name. Until #2 lands, the registry is
used independently — for example by integration tests or tooling that
needs to discover the wrappers available in the codebase.

Design goals
------------
* **Lazy imports.** Wrapper modules pull in heavyweight third-party
  dependencies (conan, cmake bindings, GitPython, etc.). The registry
  resolves modules with :func:`importlib.import_module` only on
  :meth:`get`, so importing this module is free.
* **Test-friendly.** :meth:`register` accepts a dotted module path or a
  pre-imported class so unit tests can swap implementations.
* **Read-only by default.** The default mapping is seeded at import time
  with the known wrappers in :mod:`xc_ce_utils.core_engine.wrappers`.

Usage
-----
.. code-block:: python

    from xc_ce_utils.core_engine.domain.wrapper_registry import WrapperRegistry

    wrapper_cls = WrapperRegistry.get('cmake')
    cmake = wrapper_cls(...)
    cmake.build()

    # Tests can override a name with a fake class:
    WrapperRegistry.register('cmake', FakeCMakeWrapper)
    try:
        ...
    finally:
        WrapperRegistry.reset()
"""

from __future__ import annotations

import importlib
from typing import ClassVar, Dict, Type, Union

from xc_ce_utils.core_engine.domain.exceptions import ConfigurationError

# A registry entry is either a dotted ``module:Class`` path (resolved
# lazily on first :meth:`get`) or an already-imported class object.
_RegistryEntry = Union[str, Type]


# ---------------------------------------------------------------------------
# Default wrapper map — extend as new wrappers are added.
# ---------------------------------------------------------------------------

_DEFAULT_WRAPPERS: Dict[str, str] = {
    'bazel': 'xc_ce_utils.core_engine.wrappers.rb_bazel_wrapper:RBBazelWrapper',
    'cmake': 'xc_ce_utils.core_engine.wrappers.rb_cmake_wrapper:RBCMakeWrapper',
    'make': 'xc_ce_utils.core_engine.wrappers.rb_make_wrapper:RBMakeWrapper',
    'script': 'xc_ce_utils.core_engine.wrappers.rb_script_runner:RBScriptRunner',
}


class WrapperRegistry:
    """Class-level singleton registry of build-tool wrappers."""

    _registry: ClassVar[Dict[str, _RegistryEntry]] = dict(_DEFAULT_WRAPPERS)

    # ------------------------------------------------------------------ API

    @classmethod
    def get(cls, name: str) -> Type:
        """Resolve ``name`` to its wrapper class.

        Lazily imports the target module on first call when the registry
        entry is a dotted string. Subsequent calls reuse the cached class.

        Raises:
            ConfigurationError: if ``name`` is not registered or its
                import path is malformed / cannot be imported.
        """
        if name not in cls._registry:
            available = ', '.join(sorted(cls._registry.keys()))
            msg = f"Unknown wrapper: '{name}'. Available wrappers: {available}"
            raise ConfigurationError(msg)

        entry = cls._registry[name]
        if isinstance(entry, str):
            wrapper_cls = cls._import_from_path(entry, name)
            cls._registry[name] = wrapper_cls  # cache resolved class
            return wrapper_cls
        return entry

    @classmethod
    def register(cls, name: str, target: _RegistryEntry) -> None:
        """Register a wrapper under ``name``.

        ``target`` may be a ``"package.module:Class"`` dotted path
        (resolved lazily) or a class object (used directly). Overwrites
        an existing entry with the same name.
        """
        if not isinstance(target, (str, type)):
            msg = (
                f"Wrapper target for '{name}' must be a dotted path "
                f'string or a class, got {type(target).__name__}'
            )
            raise ConfigurationError(msg)
        cls._registry[name] = target

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove ``name`` from the registry. Silent no-op if absent."""
        cls._registry.pop(name, None)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Return True if ``name`` is registered (resolved or lazy)."""
        return name in cls._registry

    @classmethod
    def available(cls) -> list:
        """Return a sorted list of registered wrapper names."""
        return sorted(cls._registry.keys())

    @classmethod
    def reset(cls) -> None:
        """Restore the registry to its default seeded state.

        Primarily intended for tests that mutate the registry.
        """
        cls._registry = dict(_DEFAULT_WRAPPERS)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _import_from_path(path: str, name: str) -> Type:
        """Import ``module:Class`` (or ``module.Class``) and return the class."""
        if ':' in path:
            module_path, _, attr = path.partition(':')
        elif '.' in path:
            module_path, _, attr = path.rpartition('.')
        else:
            msg = (
                f"Wrapper '{name}' has malformed import path '{path}'. "
                "Expected 'package.module:Class' or 'package.module.Class'."
            )
            raise ConfigurationError(msg)

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            msg = (
                f"Failed to import wrapper module '{module_path}' "
                f"for '{name}': {exc}"
            )
            raise ConfigurationError(msg) from exc

        try:
            return getattr(module, attr)
        except AttributeError as exc:
            msg = (
                f"Wrapper module '{module_path}' has no attribute "
                f"'{attr}' for wrapper '{name}'"
            )
            raise ConfigurationError(msg) from exc
