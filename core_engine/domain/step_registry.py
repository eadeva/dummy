"""
Step registry for the unified execution engine.

Provides a decorator-based registration system with metadata (category,
config_fields, env_vars) for every registered step type.
"""

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
)

from xc_ce_utils.core_engine.domain.exceptions import (
    ConfigurationError,
    ErrorRecoveryStrategy,
)

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.steps.base import ExecutionStep


# ---------------------------------------------------------------------------
# Category auto-mapping for all 76 built-in step_types
# ---------------------------------------------------------------------------

CATEGORY_MAP: Dict[str, str] = {
    # Build (10)
    'cmake_set-up': 'Build',
    'cmake_build': 'Build',
    'ctest': 'Build',
    'make': 'Build',
    'make_clean': 'Build',
    'bazel_build': 'Build',
    'bazel_test': 'Build',
    'bazel_run': 'Build',
    'bazel_clean': 'Build',
    'bazel_query': 'Build',
    # Package Management (1)
    'conan_command': 'Package Management',
    # Quality & Analysis (5)
    'docascode': 'Quality & Analysis',
    'sfa': 'Quality & Analysis',
    'sca': 'Quality & Analysis',
    'oss': 'Quality & Analysis',
    'qac': 'Quality & Analysis',
    'sbom': 'Quality & Analysis',
    # Vendor / Code Gen (5)
    'vector_davinci_configure': 'Vendor / Code Gen',
    'vector_davinci_generate': 'Vendor / Code Gen',
    'tresos_configure': 'Vendor / Code Gen',
    'tresos_generate': 'Vendor / Code Gen',
    'dng_export': 'Vendor / Code Gen',
    # Deploy & Artifacts (5)
    'deploy': 'Deploy & Artifacts',
    'artifactory_cleanup': 'Deploy & Artifacts',
    'splunk_export': 'Deploy & Artifacts',
    'art_downloader_setup': 'Deploy & Artifacts',
    'art_download': 'Deploy & Artifacts',
    'tb_installation': 'Deploy & Artifacts',
    # Hardware (20)
    't32_setup': 'Hardware',
    't32_get_state': 'Hardware',
    't32_run_cmm_script': 'Hardware',
    't32_run_cmd': 'Hardware',
    't32_erase_flash': 'Hardware',
    't32_flash_binary': 'Hardware',
    't32_flash_hex': 'Hardware',
    't32_load_elf': 'Hardware',
    't32_close': 'Hardware',
    'com_init': 'Hardware',
    'com_interrupt_boot': 'Hardware',
    'com_read': 'Hardware',
    'com_scan': 'Hardware',
    'com_scan_queue': 'Hardware',
    'com_send_cmd': 'Hardware',
    'com_close': 'Hardware',
    'voltcraft_init': 'Hardware',
    'voltcraft_power_reset': 'Hardware',
    'voltcraft_power_on': 'Hardware',
    'voltcraft_power_off': 'Hardware',
    'power_supply_init': 'Hardware',
    'power_supply_on': 'Hardware',
    'power_supply_off': 'Hardware',
    'power_supply_reset': 'Hardware',
    'power_supply_set_voltage': 'Hardware',
    'winidea_setup': 'Hardware',
    'winidea_flash_pflash': 'Hardware',
    'winidea_flash_dflash': 'Hardware',
    'winidea_flash_ucb': 'Hardware',
    'winidea_reset': 'Hardware',
    'winidea_close': 'Hardware',
    # Network (7)
    'ssh_connection_setup': 'Network',
    'ssh_run_cmd': 'Network',
    'ssh_disconnect': 'Network',
    'tftp_upload': 'Network',
    'tftp_download': 'Network',
    'tftp_server_setup': 'Network',
    'tftp_server_close': 'Network',
    # File & Binary Ops (7)
    'file_find': 'File & Binary Ops',
    'dir_find': 'File & Binary Ops',
    'file_text_log_scan': 'File & Binary Ops',
    'bin_convert_to_bin': 'File & Binary Ops',
    'bin_split_in_chunks': 'File & Binary Ops',
    'bin_convert_to_hex': 'File & Binary Ops',
    'bin_compute_file_crc': 'File & Binary Ops',
    # Shell & Scripting (2)
    'shell_run_command': 'Shell & Scripting',
    'custom_script': 'Shell & Scripting',
    # Execution Control (9)
    'variable_add': 'Execution Control',
    'variable_set': 'Execution Control',
    'choice': 'Execution Control',
    'user_input': 'Execution Control',
    'timer_start': 'Execution Control',
    'timer_stop': 'Execution Control',
    'timer_checkpoint': 'Execution Control',
    'wait_idle': 'Execution Control',
    'thread_stop': 'Execution Control',
    # Testing (9)
    'canoe_open': 'Testing',
    'canoe_start_measurement': 'Testing',
    'canoe_stop_measurement': 'Testing',
    'canoe_load_xcp_config': 'Testing',
    'canoe_set_sysvar': 'Testing',
    'canoe_execute_test_config': 'Testing',
    'canoe_execute_test_env': 'Testing',
    'canoe_execute_test_modules': 'Testing',
    'canoe_execute_yaml_tests': 'Testing',
    'canoe_ini_file': 'Testing',
    'canoe_close': 'Testing',
    'test_report_collect': 'Testing',
}


# ---------------------------------------------------------------------------
# Registry entry dataclass
# ---------------------------------------------------------------------------


@dataclass
class StepRegistryEntry:
    """Metadata stored for each registered step type."""

    step_class: Type['ExecutionStep']
    category: str
    config_fields: Dict[str, Any] = field(default_factory=dict)
    env_vars: Dict[str, str] = field(default_factory=dict)
    recovery: ErrorRecoveryStrategy = ErrorRecoveryStrategy.ABORT


# ---------------------------------------------------------------------------
# StepRegistry
# ---------------------------------------------------------------------------


class StepRegistry:
    """Registry mapping step_type strings to ExecutionStep subclasses with metadata."""

    _registry: ClassVar[Dict[str, StepRegistryEntry]] = {}

    @classmethod
    def register(
        cls,
        *step_types: str,
        category: Optional[str] = None,
        recovery: ErrorRecoveryStrategy = ErrorRecoveryStrategy.ABORT,
    ) -> Callable[[Type['ExecutionStep']], Type['ExecutionStep']]:
        """Decorator to register a step class for one or more step_type values.

        Category resolution order:
        1. Explicit ``category=`` argument to the decorator
        2. ``CATEGORY_MAP`` lookup for each step_type
        3. ``"Uncategorized"``

        Args:
            recovery: Declared :class:`ErrorRecoveryStrategy` for this step type.
                Defaults to ``ABORT`` (legacy behaviour). Currently
                metadata-only — the engine routes errors via the legacy
                ``game_stopper`` boolean. Consumed by later phases.

        Usage::

            @StepRegistry.register('cmake_build')
            class CMakeBuildStep(ExecutionStep): ...


            @StepRegistry.register('t32_setup', 't32_close', category='Hardware')
            class T32Step(ExecutionStep): ...
        """

        def decorator(step_cls: Type['ExecutionStep']) -> Type['ExecutionStep']:
            for step_type in step_types:
                cls._ensure_step_type_not_registered(step_type, step_cls)
                entry = cls._build_entry(
                    step_cls,
                    step_type,
                    category=category,
                    recovery=recovery,
                )
                cls._registry[step_type] = entry
            return step_cls

        return decorator

    @classmethod
    def _ensure_step_type_not_registered(
        cls,
        step_type: str,
        step_cls: Type['ExecutionStep'],
    ) -> None:
        """Reject duplicate step_type registration attempts."""
        if step_type not in cls._registry:
            return

        existing = cls._registry[step_type].step_class.__name__
        msg = (
            f"step_type '{step_type}' is already registered "
            f'to {existing}, cannot register {step_cls.__name__}'
        )
        raise ValueError(msg)

    @classmethod
    def _build_entry(
        cls,
        step_cls: Type['ExecutionStep'],
        step_type: str,
        *,
        category: Optional[str],
        recovery: ErrorRecoveryStrategy,
    ) -> StepRegistryEntry:
        """Create a StepRegistryEntry from class metadata and defaults."""
        resolved_category = cls._resolve_category(step_type, category)
        return StepRegistryEntry(
            step_class=step_cls,
            category=resolved_category,
            config_fields=getattr(step_cls, 'config_fields', {}),
            env_vars=getattr(step_cls, 'env_vars', {}),
            recovery=recovery,
        )

    @staticmethod
    def _resolve_category(step_type: str, category: Optional[str]) -> str:
        """Resolve category from explicit argument, map, then fallback."""
        return category or CATEGORY_MAP.get(step_type) or 'Uncategorized'

    @classmethod
    def get(cls, step_type: str) -> Type['ExecutionStep']:
        """Look up the step class for a given step_type.

        Returns the class directly (not the entry) for backward compatibility.

        Raises:
            ConfigurationError: If step_type is not registered.
        """
        return cls._get_entry(step_type).step_class

    @classmethod
    def _get_entry(cls, step_type: str) -> StepRegistryEntry:
        """Look up the full registry entry for a step_type."""
        if step_type not in cls._registry:
            available = cls._format_available_step_types()
            msg = f"Unknown step_type: '{step_type}'. Available types: {available}"
            raise ConfigurationError(msg)
        return cls._registry[step_type]

    @classmethod
    def _format_available_step_types(cls) -> str:
        """Return available step types as a stable, user-facing string."""
        return ', '.join(cls.available_types())

    @classmethod
    def get_category(cls, step_type: str) -> str:
        """Return the category for a registered step_type."""
        return cls._get_entry(step_type).category

    @classmethod
    def get_config_fields(cls, step_type: str) -> Dict[str, Any]:
        """Return the declared config_fields for a registered step_type."""
        return cls._get_entry(step_type).config_fields

    @classmethod
    def get_env_vars(cls, step_type: str) -> Dict[str, str]:
        """Return declared environment variables for a registered step_type."""
        return cls._get_entry(step_type).env_vars

    @classmethod
    def get_recovery(cls, step_type: str) -> ErrorRecoveryStrategy:
        """Return the declared :class:`ErrorRecoveryStrategy` for a step_type.

        Defaults to ``ABORT`` for step types registered without an explicit
        ``recovery=`` argument.
        """
        return cls._get_entry(step_type).recovery

    @classmethod
    def get_entries_by_category(cls) -> Dict[str, List[str]]:
        """Return step_types grouped by category."""
        by_category: Dict[str, List[str]] = {}
        for pt, entry in cls._registry.items():
            by_category.setdefault(entry.category, []).append(pt)
        return by_category

    @classmethod
    def is_registered(cls, step_type: str) -> bool:
        """Check if a step_type is registered."""
        return step_type in cls._registry

    @classmethod
    def available_types(cls) -> list:
        """Return sorted list of all registered step_type values."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls):
        """Clear the registry. Primarily for testing."""
        cls._registry.clear()
