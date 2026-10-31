"""Report model (pure): one run plus the tool results its steps produced."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..graphs import describe_graph

PASSED, FAILED, ERROR, SKIPPED = "passed", "failed", "error", "skipped"


@dataclass
class TestCase:
    name: str
    classname: str = ""
    status: str = PASSED  # passed | failed | error | skipped
    time: float = 0.0
    message: str = ""
    disposition: str = "active"
    suppression_rule: str = ""
    reason: str = ""


@dataclass
class TestSuite:
    name: str
    step: str  # label of the step whose reports folder held the file
    source: str  # file name
    cases: list[TestCase] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for c in self.cases if c.status == status)


@dataclass
class Finding:
    tool: str
    rule: str
    level: str  # error | warning | note
    message: str
    file: str = ""
    line: int | None = None
    step: str = ""
    disposition: str = "active"
    suppression_rule: str = ""
    reason: str = ""


@dataclass
class LogFinding(Finding):
    source_log: str = ""
    log_line: int = 0
    occurrences: int = 1
    log_lines: list[int] = field(default_factory=list)
    context: list[str] = field(default_factory=list)


@dataclass
class Coverage:
    step: str
    source: str
    lines_valid: int
    lines_covered: int

    @property
    def percent(self) -> float:
        return (
            100.0 * self.lines_covered / self.lines_valid if self.lines_valid else 0.0
        )


@dataclass
class Need:
    id: str
    title: str = ""
    type: str = ""
    type_name: str = ""
    status: str = ""
    tags: list[str] = field(default_factory=list)
    docname: str = ""
    line: int | None = None
    page: str = ""
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class NeedsViolation:
    need_id: str
    level: str
    rule: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    children: list[dict[str, Any]] = field(default_factory=list)
    disposition: str = "active"
    suppression_rule: str = ""
    reason: str = ""


@dataclass
class SphinxReport:
    step: str
    source: str  # directory relative to the producing step's build directory
    project: str = ""
    version: str = ""
    needs: list[Need] = field(default_factory=list)
    violations: list[NeedsViolation] = field(default_factory=list)
    needs_file: str = ""
    violations_file: str = ""
    docs_index: str = ""
    needs_imported: bool = False
    violations_imported: bool = False
    validated_needs: int | None = None
    validation_summary: str = ""


@dataclass
class CMakeReport:
    step: str
    source: str
    version: str
    importer: str
    executable: str = ""
    status: str = ""
    duration: float = 0.0
    diagnostics: list[LogFinding] = field(default_factory=list)
    configuration: dict[str, str] = field(default_factory=dict)
    toolchains: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    packages: list[dict[str, Any]] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    availability: dict[str, str] = field(default_factory=dict)


@dataclass
class BazelReport:
    step: str
    source: str
    version: str = ""
    importer: str = "bazel-bep-json"
    executable: str = ""
    invocation_id: str = ""
    command: str = ""
    workspace: str = ""
    status: str = ""
    duration: float = 0.0
    exit_code: int | None = None
    exit_name: str = ""
    complete: bool = False
    diagnostics: list[LogFinding] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    test_attempts: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    configurations: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    availability: dict[str, str] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=dict)


@dataclass
class GNReport:
    step: str
    source: str
    version: str = ""
    importer: str = "gn-project-json"
    executable: str = ""
    root: str = ""
    build_dir: str = ""
    status: str = "unknown"
    duration: float = 0.0
    exit_code: int | None = None
    diagnostics: list[LogFinding] = field(default_factory=list)
    targets: list[dict[str, Any]] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    availability: dict[str, str] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=dict)


@dataclass
class Contribution:
    step: str
    suites: list[TestSuite] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    log_findings: list[LogFinding] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # unreadable files
    sphinx: list[SphinxReport] = field(default_factory=list)
    cmake: list[CMakeReport] = field(default_factory=list)
    bazel: list[BazelReport] = field(default_factory=list)
    gn: list[GNReport] = field(default_factory=list)


@dataclass
class ReportStep:
    label: str
    kind: str
    status: str
    start: float
    duration: float
    exit_code: int | None = None
    attempts: int = 1
    message: str = ""
    command: str = ""
    log_file: str = ""
    allowed_failure: bool = False
    needs: list[str] = field(default_factory=list)
    launched_pid: int | None = None

    @property
    def name(self) -> str:
        return self.label


@dataclass
class Report:
    project: str
    job: str
    variant: str
    run_id: str
    status: str
    started_at: str
    duration: float
    params: dict[str, Any]
    param_sources: dict[str, str]
    steps: list[ReportStep]
    suites: list[TestSuite] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    log_findings: list[LogFinding] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    log_analysis_enabled: bool = False
    ptk_version: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    graph: dict[str, Any] = field(default_factory=lambda: describe_graph({}))
    sphinx: list[SphinxReport] = field(default_factory=list)
    cmake: list[CMakeReport] = field(default_factory=list)
    bazel: list[BazelReport] = field(default_factory=list)
    gn: list[GNReport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in (PASSED, SKIPPED)

    @property
    def has_errors(self) -> bool:
        """Errors worth inspecting, including tolerated failures and imported results."""
        return (
            self.status in (FAILED, ERROR)
            or any(step.status in (FAILED, ERROR) for step in self.steps)
            or any(
                case.status in (FAILED, ERROR) and case.disposition == "active"
                for suite in self.suites
                for case in suite.cases
            )
            or any(
                finding.level == ERROR and finding.disposition == "active"
                for finding in self.findings
            )
            or any(
                f.level == ERROR and f.disposition == "active"
                for f in self.log_findings
            )
            or bool(self.problems)
            or any(
                v.level == ERROR and v.disposition == "active"
                for doc in self.sphinx
                for v in doc.violations
            )
            or any(
                f.level == ERROR and f.disposition == "active"
                for cmake in self.cmake
                for f in cmake.diagnostics
            )
            or any(
                f.level == ERROR and f.disposition == "active"
                for bazel in self.bazel
                for f in bazel.diagnostics
            )
            or any(
                f.level == ERROR and f.disposition == "active"
                for gn in self.gn
                for f in gn.diagnostics
            )
        )

    def test_totals(self) -> Counter[str]:
        totals: Counter[str] = Counter()
        for suite in self.suites:
            for case in suite.cases:
                totals[case.status] += 1
        return totals

    def finding_totals(self) -> Counter[str]:
        return Counter(f.level for f in self.findings)

    def failed_steps(self) -> list[ReportStep]:
        return [s for s in self.steps if s.status in (FAILED, "cancelled")]


def from_summary(
    summary: dict[str, Any], contributions: list[Contribution], ptk_version: str = ""
) -> Report:
    steps = [
        ReportStep(
            label=s["step"],
            kind=s["kind"],
            needs=list(s["needs"]),
            status=s.get("status", "pending"),
            start=float(s.get("start", 0.0)),
            duration=float(s.get("duration", 0.0)),
            exit_code=s.get("exit_code"),
            attempts=int(s.get("attempts", 1)),
            message=s.get("message", ""),
            command=s.get("command", ""),
            log_file=s.get("log_file", ""),
            allowed_failure=bool(s.get("allowed_failure", False)),
            launched_pid=s.get("launched_pid"),
        )
        for s in summary.get("steps", [])
    ]
    graph = describe_graph({step.label: step for step in steps})
    for node, step, recorded in zip(
        graph["nodes"], steps, summary.get("steps", []), strict=True
    ):
        if not recorded.get("report", True):
            node["status"] = "hidden"
            node["message"] = "Step details excluded by report: false"
        else:
            node.update(
                status=step.status,
                duration=step.duration,
                message=step.message,
                allowed_failure=step.allowed_failure,
            )
    selection = summary.get("context", {}).get("selection", {})
    if selection.get("only_step"):
        graph["notice"] = (
            f"Only step {selection['only_step']}; prerequisites not run: "
            + (", ".join(selection["omitted_dependencies"]) or "none")
            + ". Required outputs must already exist. All configured dependency edges are retained."
        )
    report = Report(
        project=summary.get("project", ""),
        job=summary.get("job", ""),
        variant=summary.get("variant", ""),
        run_id=summary.get("run_id", ""),
        status=summary.get("status", "pending"),
        started_at=summary.get("started_at", ""),
        duration=float(summary.get("duration", 0.0)),
        params=dict(summary.get("params", {})),
        param_sources=dict(summary.get("param_sources", {})),
        steps=[
            step
            for step, recorded in zip(steps, summary.get("steps", []), strict=True)
            if recorded.get("report", True)
        ],
        graph=graph,
        ptk_version=summary.get("context", {}).get("ptk_version") or ptk_version,
        context=summary.get("context", {}),
        problems=list(summary.get("report_problems", [])),
    )
    for contribution in contributions:
        report.suites += contribution.suites
        report.findings += contribution.findings
        report.log_findings += contribution.log_findings
        report.coverage += contribution.coverage
        report.problems += contribution.problems
        report.sphinx += contribution.sphinx
        report.cmake += contribution.cmake
        report.bazel += contribution.bazel
        report.gn += contribution.gn
    return report


def test_metrics(cases) -> dict[str, int]:
    counts = Counter(case.status for case in cases)
    return {
        "Executed": sum(counts.values()) - counts[SKIPPED],
        "Passed": counts[PASSED],
        "Skipped": counts[SKIPPED],
        "Failed": counts[FAILED] + counts[ERROR],
    }
