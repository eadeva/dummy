"""Historical run metadata and test summary cards remain accurate and escaped."""

import json
import sys

from ptk.adapters.reporting import exporters, html
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.reporting.model import (
    Contribution,
    from_summary,
)
from ptk.domain.reporting.model import (
    TestCase as Case,
)
from ptk.domain.reporting.model import (
    TestSuite as Suite,
)
from ptk.domain.reporting.model import (
    test_metrics as metrics,
)
from ptk.domain.reporting.summary import run_summary


def test_test_counts_include_errors_but_not_skips_in_executed():
    cases = [
        Case("ok"),
        Case("fail", status="failed"),
        Case("error", status="error"),
        Case("skip", status="skipped"),
    ]
    assert metrics(cases) == {"Executed": 3, "Passed": 1, "Skipped": 1, "Failed": 2}
    report = from_summary(
        {
            "context": {
                "ptk_version": "1.2.3",
                "repository_alias": "engine",
                "versions": {"projects": {"engine": {"value": "<version>"}}},
                "variant": {"description": "<script>", "features": {"x": "<tag>"}},
                "tools": [{"name": "<tool>", "version": "2.0", "source": "<path>"}],
            }
        },
        [Contribution("tests", suites=[Suite("unit", "tests", "unit.xml", cases)])],
        "9.9.9",
    )
    assert report.ptk_version == "1.2.3"
    page = html.render(report)
    assert page.index("Project information") < page.index("Timeline")
    assert page.count("<dt>Executed</dt><dd>3</dd>") == 2
    assert page.count("<dt>Failed</dt><dd>2</dd>") == 2
    assert (
        "&lt;version&gt;" in page
        and "<p><script></p>" not in page
        and "&lt;script&gt;" in page
    )
    assert "&lt;path&gt;" in page
    assert json.loads(exporters.to_json(report))["totals"]["test_cases"]["Failed"] == 2
    assert "**Executed:** 3" in exporters.to_markdown(report)
    assert "Not recorded" in html.render(from_summary({}, []))


def test_run_captures_variant_versions_tools_and_survives_config_changes(write, load):
    root = write(
        {
            ".main.ptk.yml": """
project: {name: example}
repository: {alias: engine, config_path: .}
versioning:
  project: {source: literal, version: '3.4.5'}
variants:
  default: debug
  variants:
    debug: {description: Debug build}
tools:
  python:
    docker: false
    check: 'PYTHON --version'
    version: '>=3.12'
jobs:
  build:
    requires_tools: [python]
    steps:
      - hello: {run: [PYTHON, -c, 'print("hello")']}
""".replace("PYTHON", json.dumps(sys.executable))
        }
    )
    app = create_app(environ={"PTK_DOCKER": "1"})
    project = load(root)
    prepared = app.prepare_run(project).execute(project, RunRequest(job="build"))
    result = app.run_job(prepared.project).execute(prepared)
    assert result.status.value == "passed"
    summary = json.loads(json.dumps(run_summary(prepared.plan, result)))
    assert summary["context"]["variant"]["description"] == "Debug build"
    assert summary["context"]["versions"]["projects"]["engine"]["value"] == "3.4.5"
    assert summary["context"]["tools"][0]["version"]
    assert summary["context"]["tools"][0]["source"]
    project.config.versioning.project.version = "9.9.9"
    report = from_summary(summary, [], "another-ptk-version")
    assert report.ptk_version == summary["context"]["ptk_version"]
    assert report.context["versions"]["projects"]["engine"]["value"] == "3.4.5"


def test_report_header_uses_available_ptk_version_fallback():
    report = from_summary({}, [], "0.4.0+checkout")
    assert "<dt>PTK version</dt><dd>0.4.0+checkout</dd>" in html.render(report)
    assert "0.4.0+checkout" in exporters.to_markdown(report)
    recorded = from_summary({"context": {"ptk_version": "0.3.3"}}, [], "0.4.0")
    assert "<dt>PTK version</dt><dd>0.3.3</dd>" in html.render(recorded)
