"""Sphinx build evidence, retained history, report semantics and real 8.5 exports."""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from tests.project_files import read_project, write_project
from tests.workflows.test_cli import invoke, repository

from ptk.adapters.reporting import diagnostics, exporters, html, importers, sphinx
from ptk.domain.reporting.model import from_summary


def needs_data():
    return {
        "project": "Example docs",
        "current_version": "2.0",
        "versions": {
            "1.0": {"needs": {"OLD": {"id": "OLD"}}},
            "2.0": {
                "needs_defaults_removed": True,
                "needs_schema": {
                    "properties": {
                        "status": {"default": "draft"},
                        "tags": {"default": []},
                    }
                },
                "needs": {
                    "REQ_A": {
                        "id": "REQ_A",
                        "type": "req",
                        "type_name": "Requirement",
                        "title": "Power <script>window.injected=true</script>",
                        "status": "accepted",
                        "tags": ["safety"],
                        "docname": "guide.part",
                        "lineno": 8,
                        "ASIL": "QM",
                        "links": ["REQ_B"],
                    },
                    "REQ_B": {
                        "id": "REQ_B",
                        "type": "req",
                        "title": "Backup",
                        "docname": "index",
                    },
                    "DEC_C": {
                        "id": "DEC_C",
                        "type": "ddec",
                        "title": "Architecture",
                        "status": "accepted",
                    },
                },
            },
        },
    }


def violations_data():
    def record(severity, message):
        return {
            "log_lvl": "warning",
            "type": "sn_schema",
            "subtype": "local_fail",
            "details": {
                "severity": severity,
                "field": "status",
                "need_path": "REQ_A",
                "schema_path": "approved[0] > local > properties > status",
                "user_msg": message,
                "validation_msg": "Value rejected <unsafe>",
            },
            "children": [],
        }

    error = record("violation", "Status violates the requirement policy")
    error["children"] = [
        {
            "need_id": "REQ_B",
            "warning": {
                "subtype": "local_fail",
                "details": {"validation_msg": "Nested reason"},
                "children": [],
            },
        }
    ]
    return {
        "validation_summary": "Validated 3 needs",
        "validated_needs_count": 3,
        "validation_warnings": {
            "REQ_A": [error, record("info", "Inspect this relation")],
            "REQ_B": [record("warning", "Review is pending")],
        },
    }


def write_exports(root, *, needs=None, violations=True):
    folder = root / "html"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "needs.json").write_text(
        json.dumps(needs or needs_data()), encoding="utf-8"
    )
    if violations:
        (folder / "schema_violations.json").write_text(
            json.dumps(violations_data()), encoding="utf-8"
        )
    (folder / "index.html").write_text("<h1>Documentation</h1>")
    (folder / "guide.part.html").write_text('<p id="REQ_A">Requirement A</p>')
    return folder


def make_report(root):
    write_exports(root / "build/docs")
    sphinx.capture(root / "build/docs", root / "reports/docs", "docs", "passed")
    summary = {
        "job": "docs",
        "project": "example",
        "variant": "debug",
        "status": "passed",
        "steps": [{"step": "docs", "kind": "run", "needs": [], "status": "passed"}],
    }
    return from_summary(summary, importers.scan(root / "reports", {"docs": "docs"}))


def test_current_version_defaults_and_independent_severities(tmp_path):
    report = make_report(tmp_path)
    [doc] = report.sphinx
    assert [need.id for need in doc.needs] == ["REQ_A", "REQ_B", "DEC_C"]
    assert doc.needs[1].status == "draft"
    assert doc.needs[0].fields["ASIL"] == "QM"
    assert doc.needs[0].page.endswith("guide.part.html")
    assert [v.level for v in doc.violations] == ["error", "note", "warning"]
    assert doc.violations[0].children[0]["need_id"] == "REQ_B"
    assert report.status == "passed" and report.has_errors
    assert not report.test_totals()
    data = json.loads(exporters.to_json(report))
    assert data["totals"]["needs"] == {
        "records": 3,
        "types": {"req": 2, "ddec": 1},
        "statuses": {"accepted": 2, "draft": 1},
        "violations": {"error": 1, "note": 1, "warning": 1},
    }
    assert len(diagnostics.collect(report, "owner")) == 3
    page = html.render(report, link_root=tmp_path / "reports")
    assert 'data-source="sphinx"' in page
    assert "<script>window.injected=true</script>" not in page
    assert (
        "Status violates the requirement policy"
        in page.split("<h2>What failed</h2>")[1].split("</section>")[0]
    )
    assert 'data-filter="needs"' in page and "Needs by type" in page
    assert "Open docs" in page and "Nested validation details" in page
    markdown = exporters.to_markdown(report)
    assert "Sphinx documentation" in markdown and "| req | 2 |" in markdown
    assert "Open built documentation" in markdown
    # Schema violations are evidence, never invented test cases.
    assert "REQ_A" not in exporters.to_junit(report)


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_partial_build_imports_evidence_but_does_not_advertise_docs(tmp_path, status):
    write_exports(tmp_path / "build", violations=False)
    sphinx.capture(tmp_path / "build", tmp_path / "reports", "docs", status)
    [doc] = sphinx.read(tmp_path / "reports", "docs").sphinx
    assert doc.needs_imported and not doc.violations_imported
    assert doc.docs_index == "" and all(not need.page for need in doc.needs)


@pytest.mark.parametrize(
    "bad",
    [
        [],
        {},
        {"current_version": "missing", "versions": {}},
        {"current_version": "", "versions": {"": {"needs": []}}},
    ],
)
def test_malformed_needs_keeps_violation_evidence(tmp_path, bad):
    folder = write_exports(tmp_path / "build")
    (folder / "needs.json").write_text(json.dumps(bad))
    sphinx.capture(tmp_path / "build", tmp_path / "reports", "docs", "failed")
    result = sphinx.read(tmp_path / "reports", "docs")
    assert result.problems and "needs.json" in result.problems[0]
    assert not result.sphinx[0].needs_imported
    assert len(result.sphinx[0].violations) == 3


def test_empty_export_missing_validation_and_non_current_sources(tmp_path):
    data = {"current_version": "", "project": "Docs", "versions": {"": {"needs": {}}}}
    folder = write_exports(tmp_path / "build", needs=data, violations=False)
    sphinx.capture(tmp_path / "build", tmp_path / "reports", "docs", "passed")
    first = sphinx.read(tmp_path / "reports", "docs")
    assert first.sphinx[0].needs_imported and not first.sphinx[0].violations_imported
    assert first.sphinx[0].docs_index
    before = asdict(first)
    shutil.rmtree(folder)
    assert asdict(sphinx.read(tmp_path / "reports", "docs")) == before


def test_limits_and_unsafe_doc_paths(tmp_path, monkeypatch):
    data = needs_data()
    for need in data["versions"]["2.0"]["needs"].values():
        need["docname"] = "../../outside"
    write_exports(tmp_path / "build", needs=data)
    sphinx.capture(tmp_path / "build", tmp_path / "reports", "docs", "passed")
    assert all(
        not need.page
        for need in sphinx.read(tmp_path / "reports", "docs").sphinx[0].needs
    )
    monkeypatch.setattr(sphinx, "MAX_JSON_BYTES", 10)
    sphinx.capture(tmp_path / "build", tmp_path / "small", "docs", "passed")
    result = sphinx.read(tmp_path / "small", "docs")
    assert len(result.problems) == 2 and not result.sphinx[0].needs_imported


def test_workflow_build_discovery_hidden_steps_and_retained_history(tmp_path):
    writer = "from pathlib import Path; import os, shutil; target=Path(os.environ['PTK_BUILD_DIR'])/'html'; shutil.copytree('fixture/html', target, dirs_exist_ok=True)"
    root = repository(
        tmp_path,
        jobs={
            "docs": {
                "steps": {
                    "sphinx": {"run": [sys.executable, "-c", writer]},
                    "private": {"run": [sys.executable, "-c", writer], "report": False},
                }
            }
        },
        workflows={"verify": {"jobs": {"docs": {"job": "docs"}}}},
        extra={
            "layout": {"builds": "custom builds"},
            "report_formats": ["html", "json"],
        },
    )
    write_exports(root / "fixture")
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    workflow = next(root.glob("_reports/workflows/verify/*/workflow.json"))
    workflow_data = json.loads(workflow.read_text())
    [doc] = workflow_data["children"]["docs"]["sphinx"]
    assert doc["step"] == "sphinx" and len(doc["needs"]) == 3
    assert str(workflow.parent / "jobs/docs/inputs") in doc["needs_file"]
    assert Path(doc["needs_file"]).is_file()
    assert "custom builds" in doc["docs_index"]
    job = json.loads((root / "_reports/default/docs/report.json").read_text())
    first_run = job["run_id"]
    config = read_project(root / ".main.ptk.yml")
    config["jobs"]["docs"]["steps"] = {
        "replacement": {"run": [sys.executable, "-c", "print('no sphinx')"]}
    }
    write_project(root / ".main.ptk.yml", config)
    assert invoke(root, "docs").exit_code == 0
    new = json.loads((root / "_reports/default/docs/report.json").read_text())
    assert new["sphinx"] == []  # old build output is not assigned to another step
    assert (
        invoke(
            root,
            "report",
            "export",
            "docs",
            "--run",
            first_run,
            "-f",
            "json",
            "-o",
            str(root / "old"),
        ).exit_code
        == 0
    )
    old = json.loads((root / "old/report.json").read_text())
    assert len(old["sphinx"][0]["needs"]) == 3
    assert Path(old["sphinx"][0]["needs_file"]).is_file()
    assert json.loads(workflow.read_text()) == workflow_data
    assert Path(doc["needs_file"]).is_file()


def test_real_sphinx_needs_85_exports(tmp_path):
    pytest.importorskip("sphinx")
    pytest.importorskip("sphinx_needs")
    source = tmp_path / "source"
    source.mkdir()
    (source / "conf.py").write_text(
        "extensions=['sphinx_needs']\nproject='Actual docs'\nversion='1.0'\nneeds_build_json=True\nneeds_schema_definitions={'schemas':[{'id':'accepted', 'severity':'violation', 'message':'Needs must be accepted', 'validate':{'local':{'properties':{'status':{'const':'accepted'}}}}}]}\n"
    )
    (source / "index.rst").write_text(
        "Actual docs\n===========\n\n.. req:: Example\n   :id: REQ_REAL\n   :status: draft\n"
    )
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-W",
            "--keep-going",
            str(source),
            str(tmp_path / "build/html"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
    )
    assert built.returncode == 1, built.stdout + built.stderr
    sphinx.capture(tmp_path / "build", tmp_path / "reports", "sphinx", "failed")
    result = sphinx.read(tmp_path / "reports", "sphinx")
    assert not result.problems
    [doc] = result.sphinx
    assert doc.needs[0].id == "REQ_REAL"
    assert (
        doc.violations[0].level == "error" and doc.violations[0].need_id == "REQ_REAL"
    )
    assert doc.docs_index == ""


def test_capture_io_failure_is_report_evidence_not_execution_failure(
    tmp_path, monkeypatch
):
    root = repository(tmp_path, extra={"report_formats": ["json", "html"]})

    def denied(*args):
        raise OSError("snapshot write denied")

    monkeypatch.setattr(sphinx, "capture", denied)
    result = invoke(root, "build")
    assert result.exit_code == 0, result.output
    data = json.loads((root / "_reports/default/build/report.json").read_text())
    assert data["status"] == "passed"
    assert "snapshot write denied" in data["problems"][0]
    assert (
        'data-source="report"'
        in (root / "_reports/default/build/report.html").read_text()
    )


def test_multiple_exports_keep_equal_ids_and_missing_needs(tmp_path):
    write_exports(tmp_path / "build/en")
    write_exports(tmp_path / "build/de")
    (tmp_path / "build/de/html/needs.json").unlink()
    sphinx.capture(tmp_path / "build", tmp_path / "reports/docs", "docs", "passed")
    result = sphinx.read(tmp_path / "reports/docs", "docs")
    assert len(result.sphinx) == 2
    assert [doc.source for doc in result.sphinx] == ["de/html", "en/html"]
    assert not result.sphinx[0].needs_imported
    assert len(result.sphinx[0].violations) == 3
    # Separate source directories are not deduplicated by equal need IDs.
    write_exports(tmp_path / "build/de")
    sphinx.capture(tmp_path / "build", tmp_path / "reports/docs", "docs", "passed")
    report = from_summary(
        {"job": "docs", "steps": []}, [sphinx.read(tmp_path / "reports/docs", "docs")]
    )
    data = json.loads(exporters.to_json(report))
    assert data["totals"]["needs"]["records"] == 6
    assert data["totals"]["needs"]["violations"]["error"] == 2
