"""Report model (pure): one run plus the tool results its steps produced."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

PASSED, FAILED, ERROR, SKIPPED = "passed", "failed", "error", "skipped"


@dataclass
class TestCase:
    name: str
    classname: str = ""
    status: str = PASSED  # passed | failed | error | skipped
    time: float = 0.0
    message: str = ""


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
class Contribution:
    step: str
    suites: list[TestSuite] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # unreadable files


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

    @property
    def name(self) -> str:
        return self.label.rsplit("/", 1)[-1]

    @property
    def depth(self) -> int:
        return self.label.count("/")


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
    problems: list[str] = field(default_factory=list)
    ptk_version: str = ""
    context: dict[str, Any] = field(default_factory=dict)

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
                case.status in (FAILED, ERROR)
                for suite in self.suites
                for case in suite.cases
            )
            or any(finding.level == ERROR for finding in self.findings)
            or bool(self.problems)
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
        return [
            s
            for s in self.steps
            if s.status in (FAILED, "cancelled") and s.kind != "set"
        ]


def from_summary(
    summary: dict[str, Any], contributions: list[Contribution], ptk_version: str = ""
) -> Report:
    steps = [
        ReportStep(
            label=s["step"],
            kind=s.get("kind", "run"),
            status=s.get("status", "pending"),
            start=float(s.get("start", 0.0)),
            duration=float(s.get("duration", 0.0)),
            exit_code=s.get("exit_code"),
            attempts=int(s.get("attempts", 1)),
            message=s.get("message", ""),
            command=s.get("command", ""),
            log_file=s.get("log_file", ""),
            allowed_failure=bool(s.get("allowed_failure", False)),
        )
        for s in summary.get("steps", [])
    ]
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
        steps=steps,
        ptk_version=summary.get("context", {}).get("ptk_version") or ptk_version,
        context=summary.get("context", {}),
    )
    for contribution in contributions:
        report.suites += contribution.suites
        report.findings += contribution.findings
        report.coverage += contribution.coverage
        report.problems += contribution.problems
    return report


def test_metrics(cases) -> dict[str, int]:
    counts = Counter(case.status for case in cases)
    return {
        "Executed": sum(counts.values()) - counts[SKIPPED],
        "Passed": counts[PASSED],
        "Skipped": counts[SKIPPED],
        "Failed": counts[FAILED] + counts[ERROR],
    }
