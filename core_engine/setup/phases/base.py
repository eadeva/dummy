"""Base abstractions for the setup chain-of-responsibility.

A :class:`SetupPhase` represents one concern of environment setup (Conan,
Bazel, git hooks, ...).  Phases share state through a :class:`SetupContext`
which carries the live setup state dict, the loaded build configuration,
and a back-reference to the :class:`EnvironmentSetup` instance so phases can
delegate to existing mixin methods.

The intent is *behaviour preservation*: phases must not change what
``run_setup`` does today.  The orchestration loop in
``EnvironmentSetup.run_setup`` simply iterates the phases produced by
``default_setup_phases`` and calls ``should_run`` / ``run`` on each.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xc_ce_utils.core_engine.setup.environment_setup import EnvironmentSetup


@dataclass
class SetupContext:
    """Carrier for cross-phase setup state.

    Attributes
    ----------
    setup:
        Back-reference to the :class:`EnvironmentSetup` instance.  Phases
        use it to invoke existing mixin methods (``setup_conan``,
        ``_setup_git_hooks``, ``_install_vscode_extensions`` ...) and to
        access ``repo_path`` / ``project_folder`` / helper utilities.
    config:
        Build configuration loaded from ``config/main_conf.yml``.
    state:
        Mutable setup-state dictionary (the JSON persisted to
        ``.xc_ce_setup_state.json``).  Phases mutate this in place;
        ``run_setup`` saves it at the end.
    first_time_setup, force, is_ci, needs_credential_check:
        Pre-computed flags shared by multiple phases.
    """

    setup: 'EnvironmentSetup'
    config: Dict[str, Any]
    state: Dict[str, Any]
    first_time_setup: bool
    force: bool
    is_ci: bool
    needs_credential_check: bool
    extras: Dict[str, Any] = field(default_factory=dict)


class SetupPhase(ABC):
    """Abstract base class for a single setup phase.

    Subclasses implement ``should_run`` and ``run``.  Phases must be
    side-effect free in ``should_run`` (other than reading state/config)
    and must perform their work inside ``run``.
    """

    name: str = ''

    @abstractmethod
    def should_run(self, ctx: SetupContext) -> bool:
        """Return ``True`` when this phase needs to execute on this run."""

    @abstractmethod
    def run(self, ctx: SetupContext) -> None:
        """Execute the phase against the shared context."""
