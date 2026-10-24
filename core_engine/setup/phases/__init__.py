"""Chain-of-responsibility setup phases.

Each phase is a small class deciding ``should_run(ctx)`` and executing
``run(ctx)``.  Phases delegate the actual work to the existing setup mixins
on :class:`EnvironmentSetup` via the shared :class:`SetupContext`; this
keeps the migration behaviour-preserving while letting ``run_setup`` shrink
to a simple loop.
"""

from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.core_engine.setup.phases.bazel_phase import (
    BazelDiskCachePhase,
    BazelRemoteCachePhase,
)
from xc_ce_utils.core_engine.setup.phases.clang_phase import ClangSetupPhase
from xc_ce_utils.core_engine.setup.phases.conan_env_phase import (
    ApplyConanEnvPhase,
)
from xc_ce_utils.core_engine.setup.phases.conan_phase import (
    ConanSetupPhase,
    ConanToolsPhase,
)
from xc_ce_utils.core_engine.setup.phases.credentials_phase import (
    CredentialRenewalReminderPhase,
    CredentialValidationPhase,
)
from xc_ce_utils.core_engine.setup.phases.devmate_phase import DevmatePATPhase
from xc_ce_utils.core_engine.setup.phases.gemini_phase import GeminiCliPhase
from xc_ce_utils.core_engine.setup.phases.git_hooks_phase import (
    GitHooksMigrationPhase,
    GitHooksPhase,
)
from xc_ce_utils.core_engine.setup.phases.taco_phase import TacoAdapterPhase
from xc_ce_utils.core_engine.setup.phases.vscode_phase import (
    VSCodeExtensionsPhase,
)


def default_setup_phases():
    """Return the ordered list of setup phases used by ``run_setup``.

    Order is significant and must match the legacy ``run_setup`` sequence
    so existing setup-state files remain byte-compatible.
    """
    return [
        CredentialValidationPhase(),
        CredentialRenewalReminderPhase(),
        ConanSetupPhase(),
        ConanToolsPhase(),
        GitHooksMigrationPhase(),
        GitHooksPhase(),
        ClangSetupPhase(),
        ApplyConanEnvPhase(),
        BazelDiskCachePhase(),
        BazelRemoteCachePhase(),
        # VSCodeExtensionsPhase deactivated: extensions are installed on demand via
        # `config vs-code refresh-extensions`.
        DevmatePATPhase(),
        GeminiCliPhase(),
        TacoAdapterPhase(),
    ]


__all__ = [
    'ApplyConanEnvPhase',
    'BazelDiskCachePhase',
    'BazelRemoteCachePhase',
    'ClangSetupPhase',
    'ConanSetupPhase',
    'ConanToolsPhase',
    'CredentialRenewalReminderPhase',
    'CredentialValidationPhase',
    'DevmatePATPhase',
    'GeminiCliPhase',
    'GitHooksMigrationPhase',
    'GitHooksPhase',
    'SetupContext',
    'SetupPhase',
    'TacoAdapterPhase',
    'VSCodeExtensionsPhase',
    'default_setup_phases',
]
