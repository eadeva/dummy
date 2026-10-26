"""Generate an offline report fixture for browser regression checks."""

import sys
from pathlib import Path

from ptk.adapters.reporting.html import render
from ptk.domain.reporting.model import (
    Contribution,
    Finding,
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
)
if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(from_summary(summary, [contribution])), encoding="utf-8")
