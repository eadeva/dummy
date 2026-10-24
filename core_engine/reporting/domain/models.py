"""Canonical report domain entities.

The model is intentionally format-agnostic and JSON-serializable.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = '1.0.0'


@dataclass
class TestCase:
    """Normalized test case entry."""

    name: str
    classname: str
    status: str
    duration: float = 0.0
    message: str = ''
    output: str = ''
    description: str = ''
    properties: Dict[str, str] = field(default_factory=dict)
    source_file: str = ''


@dataclass
class TestSuite:
    """Normalized test suite entry."""

    name: str
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0
    timestamp: str = ''
    properties: Dict[str, str] = field(default_factory=dict)
    test_cases: List[TestCase] = field(default_factory=list)
    source_file: str = ''

    def recalculate_totals(self) -> None:
        """Recompute counters from test case statuses."""
        self.tests = len(self.test_cases)
        self.failures = sum(1 for tc in self.test_cases if tc.status == 'failed')
        self.errors = sum(1 for tc in self.test_cases if tc.status == 'error')
        self.skipped = sum(1 for tc in self.test_cases if tc.status == 'skipped')
        self.time = sum(tc.duration for tc in self.test_cases)


@dataclass
class Need:
    """A resolved need from needs.json."""

    id: str
    type: str
    title: str = ''
    description: str = ''
    status: str = ''
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    source_file: str = ''
    source_line: int = 0


@dataclass
class CoverageSummary:
    """Normalized coverage metrics."""

    lines_total: int = 0
    lines_covered: int = 0
    line_coverage_pct: float = 100.0
    branches_total: int = 0
    branches_covered: int = 0
    branch_coverage_pct: float = 100.0
    functions_total: Optional[int] = None
    functions_covered: Optional[int] = None
    function_coverage_pct: Optional[float] = None
    source_file: str = ''


@dataclass
class Finding:
    """Normalized static-analysis finding."""

    tool: str
    category: str
    rule_id: str = ''
    severity: str = 'unknown'
    message: str = ''
    file: str = ''
    line: int = 0
    column: int = 0
    status: str = 'open'
    source_file: str = ''
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class LogFinding:
    """Normalized log-analysis finding."""

    step: str
    type: str
    classification: str
    message: str = ''
    file: str = ''
    line: int = 0
    source_file: str = ''
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutionStepRecord:
    """Normalized execution-step record produced by step runtime."""

    name: str
    step_type: str
    status: str
    execution_index: Optional[int] = None
    test_status: str = 'n.a.'
    elapsed_seconds: Optional[float] = None
    elapsed_human: str = ''
    parameters: Dict[str, Any] = field(default_factory=dict)
    results: List[str] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    source_file: str = ''


@dataclass
class CanonicalReport:
    """Top-level canonical report envelope."""

    schema_version: str = SCHEMA_VERSION
    metadata: Dict[str, Any] = field(default_factory=dict)
    needs: List[Need] = field(default_factory=list)
    test_suites: List[TestSuite] = field(default_factory=list)
    coverage: List[CoverageSummary] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    log_findings: List[LogFinding] = field(default_factory=list)
    execution_steps: List[ExecutionStepRecord] = field(default_factory=list)

    def ensure_defaults(self) -> None:
        """Ensure required metadata fields are present."""
        self.metadata.setdefault('generated_at', datetime.now(timezone.utc).isoformat())

    def merge_suite(self, incoming: TestSuite) -> None:
        """Merge a suite by name, preserving grouped reporting."""
        existing = next((s for s in self.test_suites if s.name == incoming.name), None)
        if existing is None:
            incoming.recalculate_totals()
            self.test_suites.append(incoming)
            return

        existing.test_cases.extend(incoming.test_cases)
        existing.properties.update(incoming.properties)
        if incoming.timestamp and (
            not existing.timestamp or incoming.timestamp < existing.timestamp
        ):
            existing.timestamp = incoming.timestamp
        existing.recalculate_totals()

    @property
    def total_tests(self) -> int:
        return sum(s.tests for s in self.test_suites)

    @property
    def total_failures(self) -> int:
        return sum(s.failures for s in self.test_suites)

    @property
    def total_errors(self) -> int:
        return sum(s.errors for s in self.test_suites)

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.test_suites)

    @property
    def total_time(self) -> float:
        return sum(s.time for s in self.test_suites)

    @property
    def total_execution_steps(self) -> int:
        return len(self.execution_steps)

    @property
    def failed_execution_steps(self) -> int:
        return sum(1 for s in self.execution_steps if s.status.upper() == 'FAILED')

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain JSON-friendly structures."""
        self.ensure_defaults()
        data = asdict(self)
        data['summary'] = {
            'tests': self.total_tests,
            'failures': self.total_failures,
            'errors': self.total_errors,
            'skipped': self.total_skipped,
            'time': round(self.total_time, 3),
            'coverage_entries': len(self.coverage),
            'findings': len(self.findings) + len(self.log_findings),
            'static_findings': len(self.findings),
            'log_findings': len(self.log_findings),
            'execution_steps': self.total_execution_steps,
            'execution_steps_failed': self.failed_execution_steps,
        }
        return data
