"""Centralised environment-variable accessor for xc-ce-utils.

The historical pattern in this codebase reads/writes ``os.environ`` directly
from many call sites. That leaks responsibilities (type coercion, required
checks, GitHub-Actions export, logging) across the package and makes the
behaviour hard to mock in tests.

``EnvManager`` is a thin, opt-in facade providing one place to:

* Read environment variables with typed coercion and required-check.
* Write environment variables with logging.
* Export to ``$GITHUB_ENV`` when running under GitHub Actions.

It is intentionally additive: existing direct ``os.environ`` usage continues
to work. Migrating call sites to ``EnvManager`` is a separate, deliberate
diff (Phase 2 of the refactor plan).

Example
-------
>>> env = EnvManager.instance()
>>> env.set('MY_VAR', 'value')
>>> env.get('MY_VAR')
'value'
>>> env.get('MISSING', default='fallback')
'fallback'
>>> env.get(
...     'MY_INT', default=0, cast=int
... )  # cast applied to default too only if needed
"""

from __future__ import annotations

import os
from threading import Lock
from typing import Any, Callable, Optional, TypeVar

from xc_ce_utils.rb_logger import logger

T = TypeVar('T')

_MISSING = object()


class EnvManager:
    """Singleton accessor for process environment variables.

    Construction is not part of the public API; use :meth:`instance`.
    """

    _instance: Optional['EnvManager'] = None
    _lock: Lock = Lock()

    def __init__(self) -> None:
        # Constructor is public for testability (subclassing, isolated
        # instances in unit tests) but production code should use
        # :meth:`instance` to obtain the shared singleton.
        pass

    # ------------------------------------------------------------------
    # Singleton plumbing
    # ------------------------------------------------------------------
    @classmethod
    def instance(cls) -> 'EnvManager':
        """Return the process-wide :class:`EnvManager` singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_singleton_for_tests(cls) -> None:
        """Reset the singleton. **Test-only**; do not use in production."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get(
        self,
        key: str,
        default: Any = _MISSING,
        required: bool = False,
        cast: Optional[Callable[[str], T]] = None,
    ) -> Any:
        """Retrieve an environment variable.

        Parameters
        ----------
        key:
            Name of the environment variable.
        default:
            Value returned when ``key`` is not present and ``required`` is
            ``False``. If omitted, returns ``None`` for missing keys.
        required:
            When ``True`` and ``key`` is missing, raise :class:`KeyError`.
            ``default`` is ignored in this case.
        cast:
            Optional callable applied to the raw string value before
            returning. Not applied to ``default``. Common choices:
            :class:`int`, :class:`float`, :class:`pathlib.Path`, ``bool``
            via a custom helper.

        Raises
        ------
        KeyError
            If ``required=True`` and ``key`` is not in the environment.
        ValueError
            If ``cast`` raises while converting the value.
        """
        raw = os.environ.get(key)
        if raw is None:
            if required:
                raise KeyError(f'Required environment variable not set: {key}')
            return None if default is _MISSING else default

        if cast is None:
            return raw
        try:
            return cast(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f'Failed to cast environment variable {key}={raw!r} '
                f'with {cast!r}: {exc}'
            ) from exc

    def has(self, key: str) -> bool:
        """Return ``True`` when ``key`` is present in the environment."""
        return key in os.environ

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Set ``os.environ[key] = str(value)`` with debug logging."""
        os.environ[key] = str(value)
        logger.debug(f'EnvManager.set: {key}={value!r}')

    def unset(self, key: str) -> None:
        """Remove ``key`` from the environment if present."""
        if key in os.environ:
            del os.environ[key]
            logger.debug(f'EnvManager.unset: {key}')

    # ------------------------------------------------------------------
    # GitHub Actions integration
    # ------------------------------------------------------------------
    def export_to_github_env(
        self, key: str, value: Optional[Any] = None
    ) -> bool:
        """Append ``key=value`` to the file referenced by ``$GITHUB_ENV``.

        When ``value`` is ``None`` the current value of ``os.environ[key]``
        is used; this matches the common call pattern of "publish what I
        just set" without forcing callers to repeat themselves.

        Returns
        -------
        bool
            ``True`` when the value was written, ``False`` when not running
            under GitHub Actions (``$GITHUB_ENV`` unset) or when the key has
            no value to export.
        """
        github_env_file = os.environ.get('GITHUB_ENV')
        if not github_env_file:
            return False

        if value is None:
            value = os.environ.get(key)
            if value is None:
                logger.debug(
                    f'EnvManager.export_to_github_env: skipping {key} (unset)'
                )
                return False

        try:
            with open(github_env_file, 'a', encoding='utf-8') as f:
                f.write(f'{key}={value}\n')
            logger.debug(f'EnvManager.export_to_github_env: {key}={value!r}')
            return True
        except OSError as exc:
            logger.debug(
                f'EnvManager.export_to_github_env: failed for {key}: {exc}'
            )
            return False

    def set_and_export(self, key: str, value: Any) -> None:
        """Convenience: :meth:`set` then :meth:`export_to_github_env`."""
        self.set(key, value)
        self.export_to_github_env(key)


__all__ = ['EnvManager']
