"""Maintainer-only command gating for the XC-CE Utils CLI.

This module provides a single, project-wide policy for deciding whether a
given command (or YAML action) may be invoked by the current user. The
policy is driven by a ``maintainers:`` list in ``config/main_conf.yml``:

.. code-block:: yaml

    maintainers:
      - ADE7PL
      - HPG2FE

Identity is taken from :func:`xc_ce_utils.auth.rb_credentials_manager._current_user`
(the lower-cased OS user, with ``USERNAME``/``USER`` env-var override).
Matching is case-insensitive.

Behaviour
---------
* **Fail-closed**: if ``maintainers:`` is missing or empty, *nobody* is a
  maintainer. Gated commands then refuse to run with a hint pointing at
  ``config/main_conf.yml``. This is intentional: silently elevating
  everyone in unconfigured projects would leak committed files into
  random PRs.
* **Env-var override**: ``XC_CE_UTILS_FORCE_MAINTAINER=1`` bypasses the
  check. This is for CI workflows that need to run regenerators
  (release pipelines, scheduled doc rebuilds) and for emergency local
  use when the maintainers list itself is being edited.
* **Hidden by default**: maintainer commands are hidden from
  ``--help`` for non-maintainers so the dev surface stays uncluttered.

This module does **not** read configuration on its own. Callers pass in
the already-loaded ``full_config`` dict (typically
``generator.full_config``) so we stay testable and avoid duplicating
config-loading logic.
"""

from __future__ import annotations

import functools
import os
from typing import Any, Callable, Mapping, Optional

import click

from xc_ce_utils import logger
from xc_ce_utils.auth.rb_credentials_manager import _current_user

#: Environment variable that unconditionally grants maintainer rights.
FORCE_MAINTAINER_ENV = 'XC_CE_UTILS_FORCE_MAINTAINER'

#: Top-level key in ``main_conf.yml`` that holds the maintainer list.
MAINTAINERS_KEY = 'maintainers'


def _normalised_maintainers(
    full_config: Optional[Mapping[str, Any]],
) -> list[str]:
    """Return the maintainers list lower-cased, or empty if not configured."""
    if not full_config:
        return []
    raw = full_config.get(MAINTAINERS_KEY) or []
    if not isinstance(raw, list):
        return []
    return [str(entry).strip().lower() for entry in raw if str(entry).strip()]


def is_maintainer(full_config: Optional[Mapping[str, Any]]) -> bool:
    """Return ``True`` when the current user is a maintainer.

    Honours the ``XC_CE_UTILS_FORCE_MAINTAINER=1`` env-var override so
    CI and emergency edits can always run gated commands.

    Parameters
    ----------
    full_config:
        The loaded ``main_conf.yml`` dict (typically
        ``generator.full_config``). May be ``None`` during early-boot
        contexts; in that case the user is treated as non-maintainer
        unless the env-var override is set.
    """
    if os.environ.get(FORCE_MAINTAINER_ENV, '').strip() in (
        '1',
        'true',
        'True',
        'yes',
    ):
        return True
    maintainers = _normalised_maintainers(full_config)
    if not maintainers:
        return False
    return _current_user() in maintainers


def require_maintainer(full_config: Optional[Mapping[str, Any]]) -> None:
    """Raise :class:`click.ClickException` when the user is not a maintainer.

    The error message points at ``config/main_conf.yml`` so users know
    how to grant themselves access (the right answer is usually
    "ask the project maintainer to add me", but we surface the file
    path so dry runs and CI logs are self-explanatory).
    """
    if is_maintainer(full_config):
        return
    user = _current_user()
    maintainers = _normalised_maintainers(full_config)
    if not maintainers:
        hint = (
            'No maintainers are configured. Add the relevant user IDs to '
            '`maintainers:` in config/main_conf.yml, or set '
            f'{FORCE_MAINTAINER_ENV}=1 to override.'
        )
    else:
        hint = (
            f"User '{user}' is not in the maintainer list "
            f"({', '.join(maintainers)}). "
            f"Ask a maintainer to add you, or set {FORCE_MAINTAINER_ENV}=1 "
            "to override."
        )
    raise click.ClickException(hint)


def maintainer_only(
    full_config_getter: Callable[[], Optional[Mapping[str, Any]]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that gates a Click command callback to maintainers.

    Wrap a Click callback so that non-maintainers see an actionable
    refusal instead of having the command silently run. Pair this with
    Click's ``hidden=True`` on the command itself so non-maintainers
    don't even see the command in ``--help`` output (see
    :func:`hidden_for_non_maintainers`).

    The full-config is resolved through a callable so we evaluate it at
    invocation time, not at decoration time — important because the CLI
    is built in one pass before any per-command callback runs.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            require_maintainer(full_config_getter())
            return func(*args, **kwargs)

        return wrapper

    return decorator


def hidden_for_non_maintainers(
    full_config: Optional[Mapping[str, Any]],
) -> bool:
    """Return ``True`` when maintainer-only commands should be hidden.

    Use as the ``hidden=`` argument on :func:`click.command` so
    non-maintainers see a clean ``--help`` while maintainers see the
    full surface.
    """
    return not is_maintainer(full_config)


def apply_action_gating(
    cmd: click.Command,
    requires_role: Optional[str],
    full_config: Optional[Mapping[str, Any]],
) -> click.Command:
    """Apply role gating to a YAML-action Click command in place.

    Wires the contract of ``requires_role: maintainer`` in action YAML:

    * For non-maintainers, sets ``cmd.hidden = True`` so the command
      disappears from ``--help``.
    * For everyone (including maintainers), wraps the callback so the
      role check runs at invocation time — covers the case where a
      non-maintainer guesses the command name and types it anyway.

    Returns the same ``cmd`` for convenience so callers can chain.

    Currently only ``requires_role == "maintainer"`` is honoured; any
    other (or missing) value is a no-op so this is safe to call
    unconditionally.
    """
    if requires_role != 'maintainer':
        return cmd

    if hidden_for_non_maintainers(full_config):
        cmd.hidden = True

    original_callback = cmd.callback
    if original_callback is None:
        return cmd

    def _gated(
        *args: Any, _cb=original_callback, _cfg=full_config, **kwargs: Any
    ) -> Any:
        require_maintainer(_cfg)
        return _cb(*args, **kwargs)

    cmd.callback = _gated
    return cmd


def log_role_decision(full_config: Optional[Mapping[str, Any]]) -> None:
    """Emit a one-line debug log explaining the role decision.

    Helpful when users wonder why a command they expect to see is
    missing from ``--help``. Kept at debug level so it doesn't clutter
    normal output.
    """
    user = _current_user()
    maintainers = _normalised_maintainers(full_config)
    override = os.environ.get(FORCE_MAINTAINER_ENV, '').strip() in (
        '1',
        'true',
        'True',
        'yes',
    )
    logger.debug(
        f'role-gating: user={user}, maintainers={maintainers}, '
        f'force_override={override}, is_maintainer={is_maintainer(full_config)}'
    )
