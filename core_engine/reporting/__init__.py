"""Clean-architecture reporting pipeline (v2).

This package contains a layered reporting implementation:
- domain: canonical report model
- application: use-case orchestration and ports
- adapters: format-specific importers/exporters
"""

from xc_ce_utils.core_engine.reporting.factory import (
    build_default_reporting_pipeline,
)

__all__ = ['build_default_reporting_pipeline']
