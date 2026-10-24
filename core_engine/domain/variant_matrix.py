"""
Variant Configuration Loader

This module handles variant-specific configuration loading and environment variable setup.
It's focused solely on variant matrix operations and environment management.
"""

import copy
import os

# Add the xc_ce_utils path if not preset in python path to enable absolute imports
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

xc_ce_utils_path = str(Path(__file__).resolve().parent.parent.parent.parent)
if xc_ce_utils_path not in sys.path:
    sys.path.insert(0, xc_ce_utils_path)

from xc_ce_utils import logger


class Variant:
    """
    Represents a single variant dimension with its possible values and default.
    """

    def __init__(
        self,
        variant_values: Dict[str, str],
        variant_dict: Dict[str, Any],
        global_defaults: Dict[str, Any],
        default_version: Optional[Dict[str, Any]] = None,
        version_resolver: Optional[Callable[[str], Dict[str, Any]]] = None,
        default_version_pattern: Optional[str] = None,
    ):
        self.raw_dict = variant_dict
        self.variant_values = variant_values
        self.alias = str(variant_dict.get('alias'))
        self.variant_path = None
        if self.alias is None:
            raise Exception('Variant alias is required for each variant.')
        # RB_VERSIONING 'variant-git-managed': 'version' is the variant's git tag pattern,
        # resolved on first use so variants without a matching tag only fail when built.
        self._version_resolver = version_resolver
        self.version_pattern = None
        if version_resolver is not None:
            raw_version = variant_dict.get('version')
            if raw_version is not None and not isinstance(raw_version, str):
                raise Exception(
                    f"RB_VERSIONING is 'variant-git-managed': 'version' of variant "
                    f"'{self.alias}' must be a git tag pattern (e.g. 'v1.*'), got {raw_version!r}"
                )
            self.version_pattern = raw_version or default_version_pattern
            self.version = {}
        else:
            # Falls back to the globally-resolved RB_VERSIONING value (whichever mode -
            # git-managed or static file) when this variant has no version of its own.
            self.version = variant_dict.get('version') or default_version or {}
        self.description = variant_dict.get('description', '')

        self.options = {}

        self.settings = copy.deepcopy(global_defaults.get('settings', {}))
        self.requires = copy.deepcopy(global_defaults.get('requires', {}))
        self.tool_requires = copy.deepcopy(global_defaults.get('tool_requires', {}))
        self.test_requires = copy.deepcopy(global_defaults.get('test_requires', {}))
        self.build_options = copy.deepcopy(global_defaults.get('build_options', {}))
        self.calibration_variants = []

        # Generator configuration paths
        self.vector_conf = variant_dict.get('vector_conf', global_defaults.get('vector_conf'))
        self.tresos_conf = variant_dict.get('tresos_conf', global_defaults.get('tresos_conf'))

        self._set_final_options_settings_and_requirements(variant_dict)

    def get_variant_alias(self) -> str:
        """Get the alias for this variant."""
        return self.alias

    def get_version(self) -> Dict[str, Any]:
        """Get the version dict of this variant (resolved from git for 'variant-git-managed')."""
        if self._version_resolver is not None and not self.version:
            self.version = self._version_resolver(self.version_pattern)
        return self.version

    def get_features(self) -> List[str]:
        """Get the features for this variant."""
        return self.features

    def get_valued_features(self) -> Dict[str, Any]:
        """Get the valued features for this variant."""
        return self.valued_features

    def get_settings(self) -> Dict[str, Any]:
        """Get the settings for this variant."""
        return self.settings

    def get_build_options(self) -> Dict[str, Any]:
        """Get the options for this variant."""
        return self.build_options

    def get_calibration_variants(self) -> List[str]:
        """Get the calibration variants for this variant."""
        return self.calibration_variants

    def get_description(self) -> str:
        """Get the description for this variant."""
        return self.description

    def get_requires(self) -> Dict[str, Any]:
        """Get the requires for this variant."""
        return self.requires

    def get_tool_requires(self) -> Dict[str, Any]:
        """Get the tool_requires for this variant."""
        return self.tool_requires

    def get_test_requires(self) -> Dict[str, Any]:
        """Get the test_requires for this variant."""
        return self.test_requires

    def get_raw_dict(self) -> Dict[str, Any]:
        """Get the original raw variant dictionary containing only overrides."""
        return self.raw_dict

    def get_variant_values(self) -> Dict[str, str]:
        """Get the variant values for this variant."""
        return self.variant_values

    def get_variant_path(self) -> str:
        """Get the variant values for this variant."""
        return self.variant_path

    def get_vector_conf(self) -> Optional[str]:
        """Get the Vector DaVinci configuration file path for this variant."""
        return self.vector_conf

    def get_tresos_conf(self) -> Optional[str]:
        """Get the TRESOS configuration file path for this variant."""
        return self.tresos_conf

    def _set_final_options_settings_and_requirements(self, variant_dict: Dict[str, Any]):
        for setting, setting_value in variant_dict.get('settings', {}).items():
            self.settings[setting] = setting_value

        for bo_name, bo_value in variant_dict.get('build_options', {}).items():
            self.build_options[bo_name] = bo_value

        for req_name, req_conf in variant_dict.get('requires', {}).items():
            self.requires[req_name] = req_conf

        for req_name, req_conf in variant_dict.get('tool_requires', {}).items():
            self.tool_requires[req_name] = req_conf

        for req_name, req_conf in variant_dict.get('test_requires', {}).items():
            self.test_requires[req_name] = req_conf

        self.calibration_variants = variant_dict.get('calibration_variants', [])

    def get_variant_dict(self) -> Dict[str, Any]:
        """Get the full variant dictionary."""
        return {
            'alias': self.alias,
            'version': self.version,
            'version_pattern': self.version_pattern,
            'description': self.description,
            'settings': self.settings,
            'build_options': self.build_options,
            'calibration_variants': self.calibration_variants,
            'requires': self.requires,
            'tool_requires': self.tool_requires,
            'test_requires': self.test_requires,
            'variant_values': self.variant_values,
            'variant_path': self.variant_path,
            'vector_conf': self.vector_conf,
            'tresos_conf': self.tresos_conf,
        }


class VariantMatrix:
    """
    Represents the variant matrix structure and provides methods to access variant dimensions and defaults.
    """

    def __init__(
        self,
        project_conf: Dict[str, Any],
        default_version: Optional[Dict[str, Any]] = None,
        version_resolver: Optional[Callable[[str], Dict[str, Any]]] = None,
        default_version_pattern: Optional[str] = None,
    ):
        """
        Initialize with the variant configuration.

        Args:
            variant_config: The full project config including variant_matrix and variant_combinations
            default_version: Fallback version dict (e.g. the globally-resolved RB_VERSIONING
                value) applied to any variant that doesn't define its own ``version:`` field.
            version_resolver: For RB_VERSIONING 'variant-git-managed': resolves a variant's
                git tag pattern into its version dict.
            default_version_pattern: Tag pattern of variants without ``version:`` in that mode.
        """
        self.variants: Dict[str, Variant] = {}
        self.variants_by_alias: Dict[str, Variant] = {}
        self.variant_matrix_path = ''
        self.descriptions: Dict[str, str] = {}
        self.default_variant: str = None
        self.variant_level_possible_values: Dict[str, List[str]] = {}
        self.global_defaults = project_conf.get('global_defaults', {})
        self.default_version = default_version or {}
        self.version_resolver = version_resolver
        self.default_version_pattern = default_version_pattern
        self.options = {}
        self.default_options = {}

        if 'variant_matrix' not in project_conf:
            raise Exception("No 'variant_matrix' found in project configuration")

        if 'variants' not in project_conf:
            raise Exception("No 'variants' configured in project configuration")

        self.variants_config = project_conf['variants']
        self._parse_variant_matrix(project_conf)

    def get_variants(self) -> Dict[str, Variant]:
        """Get all parsed variants."""
        return self.variants

    def get_variants_by_alias(self) -> Dict[str, Variant]:
        """Get all parsed variants."""
        return self.variants_by_alias

    def list_variants(self):
        logger.info('Available variants:')
        for variant_path, variant in self.variants.items():
            logger.info(f' - {variant_path}: {variant.description}')

    def get_variant_level_possible_values(self, variant_level) -> List[str]:
        """Get the list of variant levels."""
        return list(self.variant_level_possible_values[variant_level])

    def get_default_variant(self):
        """Get default variant."""
        return self.default_variant

    def get_default_variant_alias(self):
        """Get default variant."""
        return self.variants[self.default_variant].get_variant_alias()

    def get_variant_by_alias(self, alias: str) -> Variant:
        # Just get the variant by index from the variants dict
        if alias not in self.variants_by_alias:
            raise Exception(
                f'Variant alias {alias} unknown. Available variants are {self.variants_by_alias.keys()}'
            )

        return self.variants_by_alias[alias]

    def get_variant_by_alias_or_path(self, alias_or_path: str) -> Variant:
        """Get variant by alias or path (supports both dash and slash separators).

        Args:
            alias_or_path: Variant alias (e.g., '1') or path (e.g., 'platform-tc397' or 'platform/tc397')

        Returns:
            Variant object

        Raises:
            Exception: If variant not found by alias or path
        """
        # Try alias lookup first (most common case)
        if alias_or_path in self.variants_by_alias:
            return self.variants_by_alias[alias_or_path]

        # Try path lookup with dash→slash conversion (GitHub Actions format)
        path_with_slashes = alias_or_path.replace('-', '/')
        if path_with_slashes in self.variants:
            return self.variants[path_with_slashes]

        # Try path as-is (handle slash paths directly)
        if alias_or_path in self.variants:
            return self.variants[alias_or_path]

        # Not found - provide helpful error message
        available_aliases = list(self.variants_by_alias.keys())
        available_paths = list(self.variants.keys())
        raise Exception(
            f"Variant '{alias_or_path}' not found.\n"
            f'Available aliases: {available_aliases}\n'
            f'Available paths: {available_paths}'
        )

    def _parse_variant_matrix(self, variant_config: Dict[str, Any]) -> None:
        for variant_level_name, variant_level_conf in variant_config['variant_matrix'].items():
            self._parse_variant_level(variant_level_name, variant_level_conf)

    def _parse_variant_level(
        self, variant_level_name: str, variant_level_conf: Dict[str, Any]
    ) -> None:
        self.variant_matrix_path += f'/{variant_level_name}'
        self.variant_level_possible_values[variant_level_name] = []
        self.descriptions[variant_level_name] = variant_level_conf.get('description', '')

        if 'subvariants' in variant_level_conf:
            for sub_variant_name, sub_variant_conf in variant_level_conf['subvariants'].items():
                self._parse_variant_level(sub_variant_name, sub_variant_conf)
        else:
            self.variant_matrix_path = self.variant_matrix_path.lstrip('/')
            self._parse_variants(self.variants_config)

    def _add_possible_value_to_current_level_variant(self, depth: int, value: str):
        """Add a possible value to the current level variant."""
        if depth >= len(self.variant_matrix_path.split('/')):
            raise Exception('Depth exceeds variant matrix levels')

        if (
            value
            not in self.variant_level_possible_values[self.variant_matrix_path.split('/')[depth]]
        ):
            variant_option_name = self.variant_matrix_path.split('/')[depth]
            self.variant_level_possible_values[variant_option_name].append(value)
            if variant_option_name not in self.options:
                self.options[variant_option_name] = []

            self.options[self.variant_matrix_path.split('/')[depth]].append(value)

    def _parse_variants(self, variant_config: Dict[str, Any]) -> None:
        """
        Parse the variant configuration to extract variant dimensions.

        Args:
            variant_config: The full project config including variant_matrix and variant_combinations
        """
        current_depth = 0
        for variant_name, variant_conf in variant_config.items():
            current_variant_path = variant_name
            self._add_possible_value_to_current_level_variant(current_depth, variant_name)

            os.environ[f'BO_{variant_name.upper()}'] = '0'
            logger.debug(f'Decativated variant build option: BO_{variant_name.upper()}=0')
            self._parse_variant(current_depth, current_variant_path, variant_conf)

    def _parse_variant(
        self,
        current_depth: int,
        current_path: str,
        variant_dict: Dict[str, Any],
    ) -> None:
        new_current_path_depth = current_depth + 1
        # 'alias' (not 'version', which is now optional - see default_version fallback)
        # is the reliable signal that this dict is a leaf variant rather than another
        # nesting level of the variant matrix.
        if 'alias' not in variant_dict:
            for variant_name, variant_conf in variant_dict.items():
                new_current_path = f'{current_path}/{variant_name}'
                os.environ[f'BO_{variant_name.upper()}'] = '0'
                logger.debug(f'Dectivated variant build option: BO_{variant_name.upper()}=0')
                self._add_possible_value_to_current_level_variant(
                    new_current_path_depth, variant_name
                )
                self._parse_variant(new_current_path_depth, new_current_path, variant_conf)
        else:
            if current_path in self.variants:
                raise Exception(f'Duplicate variant path found: {current_path}')

            default_variant = False
            if variant_dict.get('default'):
                default_variant = True

            variant_values = {}
            path_levels = self.variant_matrix_path.split('/')
            path_values = current_path.split('/')
            for i, level in enumerate(path_values):
                variant_values[path_levels[i]] = level
                if default_variant:
                    self.default_options[path_levels[i]] = level

            self.variants[current_path] = Variant(
                variant_values,
                variant_dict,
                self.global_defaults,
                self.default_version,
                self.version_resolver,
                self.default_version_pattern,
            )
            self.variants_by_alias[self.variants[current_path].get_variant_alias()] = self.variants[
                current_path
            ]
            # Use underscore for filesystem compatibility
            self.variants[current_path].variant_path = current_path.replace('/', '_')

            if default_variant:
                self.default_variant = current_path

    def to_dict(self) -> Dict[str, Any]:
        """Convert the variant matrix to a dictionary representation"""
        return {
            'variant_levels': self.variant_matrix_path.split('/'),
            'default_variant': self.default_variant
            if self.default_variant
            else self.variants.items()[0].get_variant_path(),
            'variant_matrix_path': self.variant_matrix_path,
            'variants': {
                variant_path: variant.get_variant_dict()
                for variant_path, variant in self.variants.items()
            },
            'options': self.options,
            'default_options': self.default_options,
        }
