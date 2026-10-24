"""Section renderers for HTML unified report."""

from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.advanced_help_section import (
    render_advanced_help_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.arch2needs_section import (
    render_arch2needs_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.coverage_section import (
    render_coverage_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.dependencies_section import (
    render_dependencies_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.execution_section import (
    render_execution_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.log_findings_section import (
    render_log_findings_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.needs_section import (
    render_needs_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.sbom_section import (
    render_sbom_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.static_findings_section import (
    render_static_findings_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.taco_section import (
    render_taco_section,
)
from xc_ce_utils.core_engine.reporting.adapters.exporters.html_sections.tests_section import (
    render_tests_section,
)

__all__ = [
    'render_advanced_help_section',
    'render_arch2needs_section',
    'render_coverage_section',
    'render_dependencies_section',
    'render_execution_section',
    'render_log_findings_section',
    'render_needs_section',
    'render_sbom_section',
    'render_static_findings_section',
    'render_taco_section',
    'render_tests_section',
]
