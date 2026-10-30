"""Generate an offline report fixture for browser regression checks."""

import sys
from pathlib import Path

from ptk.adapters.reporting.html import render
from ptk.domain.reporting.model import (
    Contribution,
    Finding,
    LogFinding,
    TestCase,
    TestSuite,
    from_summary,
)

summary = {
    "project": "PTK",
    "job": "test",
    "variant": "debug",
    "status": "failed",
    "run_id": "preview",
    "params": {"jobs": 4},
    "context": {
        "ptk_version": "0.1.2",
        "repository_alias": "ptk",
        "versions": {"projects": {"ptk": {"value": "1.2.3+4.gabc"}}},
        "variant": {
            "name": "debug",
            "description": "Debug with runtime checks",
            "components": ["core"],
            "features": {"CHECKS": True},
        },
        "tools": [
            {
                "name": "cmake",
                "version": "3.30.9",
                "required": ">=3.28",
                "source": "/tools/cmake/3.30.9/bin/cmake",
            }
        ],
    },
}
contribution = Contribution(
    "pytest",
    suites=[
        TestSuite(
            "unit",
            "pytest",
            "tests.xml",
            [
                TestCase("test_parse", "parser"),
                TestCase("test_bad", "parser", "failed"),
                TestCase("test_skip", "io", "skipped"),
                TestCase("test_error", "io", "error"),
            ],
        )
    ],
    findings=[Finding("ruff", "F401", "warning", "Unused import", "app.py", 3)],
    log_findings=[
        LogFinding(
            "log-analyzer",
            "pytest.failed",
            "error",
            "tests/test_api.py::test_bad: AssertionError: <expected>",
            step="pytest",
            source_log="pytest.log",
            log_line=10,
            log_lines=[10],
            context=[
                "9: short test summary info",
                "10: FAILED tests/test_api.py::test_bad",
            ],
        ),
        LogFinding(
            "log-analyzer",
            "",
            "warning",
            "SDK function deprecated",
            step="compile",
            source_log="compile.log",
            log_line=1,
            log_lines=[1, 2],
            occurrences=2,
        ),
        LogFinding(
            "log-analyzer",
            "",
            "warning",
            "Known SDK warning",
            step="compile",
            disposition="justified",
            reason="Upgrade pending",
            suppression_rule="sdk",
            source_log="compile.log",
            log_line=3,
            log_lines=[3],
        ),
        LogFinding(
            "log-analyzer",
            "",
            "error",
            "Expected negative test",
            step="pytest",
            disposition="ignored",
            reason="Negative test",
            suppression_rule="negative",
            source_log="pytest.log",
            log_line=4,
            log_lines=[4],
        ),
    ],
)
if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    report = from_summary(summary, [contribution])
    report.log_analysis_enabled = True
    path.write_text(render(report), encoding="utf-8")
