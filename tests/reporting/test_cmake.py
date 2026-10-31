"""Versioned CMake evidence, current invocations, warnings and report dispositions."""

import json
import os
import shutil
from dataclasses import asdict

import pytest
from tests.workflows.test_cli import invoke, repository

from ptk.adapters.process import SubprocessRunner
from ptk.adapters.reporting import cmake, exporters, html
from ptk.adapters.reporting.cmake_importers import select
from ptk.adapters.reporting.cmake_importers.common import (
    console_diagnostics,
    sarif_diagnostics,
)
from ptk.domain.execution.model import CommandSpec
from ptk.domain.reporting.model import CMakeReport, from_summary


@pytest.mark.parametrize(
    "version,expected",
    [
        ((3, 2, 0), "cmake-3.2"),
        ((3, 19, 8), "cmake-3.2"),
        ((3, 26, 0), "cmake-3.2"),
        ((3, 30, 9), "cmake-3.2"),
        ((4, 0, 3), "cmake-3.2"),
        ((4, 1, 0), "cmake-4.1"),
        ((4, 10, 1), "cmake-4.1"),
        ((5, 0, 0), "cmake-4.1"),
    ],
)
def test_version_boundary(version, expected):
    assert select(version).name == expected


def test_unsupported_version_is_explicit():
    with pytest.raises(ValueError, match="3.2"):
        select((3, 1, 9))


def test_console_warning_categories_windows_locations_and_multiline():
    lines = [
        "CMake Warning (dev) at C:\\src\\CMakeLists.txt:8 (message):",
        "  Accepted warning",
        "",
        "CMake Deprecation Warning at CMakeLists.txt:9 (message):",
        "  Old interface",
        "",
        "CMake Error in CMakeLists.txt:",
        "  Configuration problem",
        "",
        "probe.c:10: error: deliberate feature probe",
        "-- Performing Test CHECK_X - Failed",
    ]
    findings = console_diagnostics(lines, "configure")
    assert len(findings) == 3
    assert [f.level for f in findings] == ["warning", "warning", "error"]
    assert findings[0].file == r"C:\src\CMakeLists.txt" and findings[0].line == 8
    assert findings[0].message == "Accepted warning"
    assert findings[2].message == "Configuration problem"


def test_sarif_template_message_and_duplicate_source_merge():
    data = {
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CMake",
                        "rules": [
                            {
                                "id": "CMake.Warning",
                                "messageStrings": {
                                    "default": {"text": "CMake Warning: {0}"}
                                },
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "CMake.Warning",
                        "level": "warning",
                        "message": {"id": "default", "arguments": ["Accepted warning"]},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "/src/CMakeLists.txt"},
                                    "region": {"startLine": 8},
                                }
                            }
                        ],
                    }
                ],
            }
        ]
    }
    sarif = sarif_diagnostics(data, "configure")
    console = console_diagnostics(
        ["CMake Warning at CMakeLists.txt:8 (message):", "  Accepted warning"],
        "configure",
    )
    merged = cmake.merge_diagnostics(sarif, console, source_root="/src")
    assert len(merged) == 1
    assert merged[0].message == "Accepted warning"
    assert merged[0].context == ["Source: CMake SARIF", "Source: CMake console"]


def test_32_cache_and_probe_logs_do_not_invent_errors(tmp_path):
    (tmp_path / "CMakeFiles").mkdir()
    (tmp_path / "CMakeCache.txt").write_text(
        "CMAKE_GENERATOR:INTERNAL=Unix Makefiles\nCMAKE_C_COMPILER:FILEPATH=/opt/compiler\n"
    )
    (tmp_path / "CMakeFiles/CMakeError.log").write_text(
        "Checking absent feature failed:\nerror: expected failure"
    )
    report = CMakeReport(
        "configure", str(tmp_path), "3.2.3", "cmake-3.2", status="passed"
    )
    problems = []
    select((3, 2, 3)).collect(report, tmp_path, {}, (3, 2, 3), problems)
    assert not problems and not report.diagnostics
    assert report.configuration["CMAKE_GENERATOR"] == "Unix Makefiles"
    assert report.checks[0]["result"] == "unclassified"
    assert "3.20" in report.availability["targets"]


def source(root, *, fail=False):
    root.mkdir(parents=True, exist_ok=True)
    (root / "CMakeLists.txt").write_text(
        """cmake_minimum_required(VERSION 3.10)
project(Example C)
include(CheckCSourceCompiles)
check_c_source_compiles("#error unsupported feature" HAVE_OPTIONAL_FEATURE)
find_package(DefinitelyAbsentPTK QUIET)
message(WARNING "Known SDK warning")
message(AUTHOR_WARNING "Developer review")
message(DEPRECATION "Old API")
add_library(core STATIC core.c)
add_executable(app app.c)
target_link_libraries(app PRIVATE core)
"""
        + ('message(FATAL_ERROR "Cannot configure this variant")\n' if fail else "")
    )
    (root / "core.c").write_text("void core(void) {}\n")
    (root / "app.c").write_text("int main(void) { return 0; }\n")


@pytest.fixture(params=["3", "4"])
def executable(request):
    if request.param == "4":
        value = os.environ.get("PTK_TEST_CMAKE41")
        if not value:
            pytest.skip(
                "Set PTK_TEST_CMAKE41 for the optional native CMake 4.1+ integration"
            )
        return value
    value = shutil.which("cmake")
    assert value, "CMake 3.30 is a development dependency"
    return value


def run_native(root, executable, *, fail=False, before=None):
    source(root / "source", fail=fail)
    build, reports = root / "build", root / "reports"
    command = CommandSpec(
        argv=[executable, "-S", str(root / "source"), "-B", str(build)],
        cwd=str(root),
        env={
            **os.environ,
            "PTK_BUILD_DIR": str(build),
            "PTK_STEP_REPORTS_DIR": str(reports),
            "PTK_STEP": "configure",
        },
        timeout=30,
    )
    problems, output = [], []
    outcome = cmake.CMakeReportingRunner(SubprocessRunner(), "linux").run(
        command, output.append, mask=lambda text: text, on_problem=problems.append
    )
    imported = cmake.read(reports, "configure")
    assert not problems and not imported.problems, (problems, imported.problems, output)
    return outcome, imported


def test_real_native_capture_success_warnings_probes_and_targets(tmp_path, executable):
    outcome, imported = run_native(tmp_path, executable)
    assert outcome.exit_code == 0
    [report] = imported.cmake
    assert report.executable == executable
    assert len(report.diagnostics) == 3, asdict(report)
    assert all(f.level == "warning" for f in report.diagnostics)
    assert any(check["result"] == "not-supported" for check in report.checks)
    assert {target["name"] for target in report.targets} == {"app", "core"}
    if report.importer == "cmake-4.1":
        assert any(
            p["name"] == "DefinitelyAbsentPTK" and not p["found"]
            for p in report.packages
        )
        assert all("Source: CMake SARIF" in f.context for f in report.diagnostics)
    full = from_summary({"job": "build", "status": "passed", "steps": []}, [imported])
    assert not full.has_errors and not full.test_totals()
    assert 'data-source="cmake"' in html.render(full)
    assert "CMake warnings" in html.render(full)
    assert "cmake" in json.loads(exporters.to_json(full))
    assert "CMake" in exporters.to_markdown(full)
    assert "HAVE_OPTIONAL_FEATURE" not in exporters.to_junit(full)
    shutil.rmtree(tmp_path / "build")
    assert asdict(cmake.read(tmp_path / "reports", "configure")) == asdict(imported)


def test_failed_reconfigure_does_not_reuse_previous_targets(tmp_path, executable):
    run_native(tmp_path, executable)
    shutil.rmtree(tmp_path / "reports")
    outcome, imported = run_native(tmp_path, executable, fail=True)
    assert outcome.exit_code != 0
    [report] = imported.cmake
    assert not report.targets
    assert any(
        f.level == "error" and "Cannot configure" in f.message
        for f in report.diagnostics
    )
    # The cached feature check is not a new event on the second configure.
    assert not any("HAVE_OPTIONAL_FEATURE" in c["name"] for c in report.checks)


def test_actual_step_path_selection_rules_deduplication_and_workflow(
    tmp_path, executable
):
    root = repository(
        tmp_path,
        jobs={
            "build": {
                "steps": {
                    "configure": {
                        "run": [executable, "-S", "source", "-B", "${run.build_dir}"]
                    }
                }
            }
        },
        workflows={"verify": {"jobs": {"build": {"job": "build"}}}},
        extra={
            "report_formats": ["html", "json"],
            "log_analysis": {
                "rules": [
                    {
                        "id": "sdk",
                        "match": {
                            "step": "configure",
                            "severity": "warning",
                            "message_regex": "Known SDK warning",
                        },
                        "action": "justify",
                        "reason": "Reviewed upstream",
                    },
                    {
                        "id": "old",
                        "match": {"message_regex": "Old API"},
                        "action": "ignore",
                        "reason": "Removal planned",
                    },
                ]
            },
        },
    )
    source(root / "source")
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    report = json.loads((root / "_reports/default/build/report.json").read_text())
    [cm] = report["cmake"]
    assert {f["disposition"] for f in cm["diagnostics"]} == {
        "active",
        "ignored",
        "justified",
    }
    assert not report["log_findings"], report["log_findings"]
    page = (root / "_reports/default/build/diagnostics.html").read_text()
    assert page.count('class="diagnostic"') == 3
    assert (
        'data-disposition="justified"' in page and 'data-disposition="ignored"' in page
    )
    assert "Reviewed upstream" in page
    workflow = next(root.glob("_reports/workflows/verify/*/workflow.json"))
    data = json.loads(workflow.read_text())
    assert data["children"]["build"]["cmake"][0]["version"] == cm["version"]
    assert (workflow.parent / "diagnostics.html").is_file()


def test_oversized_and_escaping_artifacts_are_report_problems(tmp_path, monkeypatch):
    from ptk.adapters.reporting.cmake_importers import common

    (tmp_path / "CMakeFiles").mkdir()
    path = tmp_path / "CMakeFiles/CMakeOutput.log"
    path.write_text("probe output")
    monkeypatch.setattr(common, "MAX_BYTES", 2)
    report = CMakeReport(
        "configure", str(tmp_path), "3.2.3", "cmake-3.2", status="passed"
    )
    problems = []
    select((3, 2, 3)).collect(report, tmp_path, {}, (3, 2, 3), problems)
    assert "exceeds" in problems[0]


def test_unchanged_cache_not_assigned_to_unrelated_command(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "CMakeCache.txt").write_text(
        "CMAKE_CACHE_MAJOR_VERSION:INTERNAL=4\nCMAKE_CACHE_MINOR_VERSION:INTERNAL=1\nCMAKE_CACHE_PATCH_VERSION:INTERNAL=3\n"
    )
    import sys

    command = CommandSpec(
        argv=[sys.executable, "-c", "print('unrelated')"],
        cwd=str(tmp_path),
        env={
            **os.environ,
            "PTK_BUILD_DIR": str(build),
            "PTK_STEP_REPORTS_DIR": str(tmp_path / "reports"),
            "PTK_STEP": "other",
        },
    )
    cmake.CMakeReportingRunner(SubprocessRunner(), "linux").run(
        command, lambda _: None, mask=lambda text: text, on_problem=pytest.fail
    )
    assert not cmake.read(tmp_path / "reports", "other").cmake


def test_masking_occurs_before_json_encoding_and_duplicate_occurrences():
    secret = 'secret"with\\escapes'
    masked = cmake.mask_data(
        {"message": secret, "nested": [secret]},
        lambda text: text.replace(secret, "********"),
    )
    assert json.loads(json.dumps(masked)) == {
        "message": "********",
        "nested": ["********"],
    }
    findings = console_diagnostics(
        ["CMake Warning: repeated", "", "CMake Warning: repeated"], "configure"
    )
    [merged] = cmake.merge_diagnostics([], findings)
    assert merged.occurrences == 2
    assert merged.context == ["Source: CMake console"]


def test_simple_shell_positional_and_preset_detection(tmp_path):
    command = CommandSpec(
        shell='"/opt/cmake path/cmake" -S source -B "build path"', cwd=str(tmp_path)
    )
    words, build = cmake.configure_command(command, "linux")
    assert words[0] == "/opt/cmake path/cmake" and build == tmp_path / "build path"
    assert (
        cmake.configure_command(
            CommandSpec(argv=["cmake", "--preset", "debug"]), "linux"
        )
        is None
    )
    assert (
        cmake.configure_command(
            CommandSpec(shell="cmake -S . -B build && echo done"), "linux"
        )
        is None
    )
    assert (
        cmake.configure_command(
            CommandSpec(argv=["cmake", "--build", "build"]), "linux"
        )
        is None
    )


def test_direct_version_query_uses_child_path_and_capability_gates(tmp_path):
    from ptk.application.ports import ProcessOutcome

    build = tmp_path / "build"
    build.mkdir()
    commands = []

    class Runner:
        def which(self, program, path=None):
            assert program == "cmake" and path == "child-path"
            return "/chosen/cmake"

        def run(self, command, out, cancel=None):
            commands.append(command)
            assert command.env["PATH"] == "child-path"
            if command.argv == ["/chosen/cmake", "--version"]:
                out("cmake version 3.2.3")
            else:
                assert command.argv == ["/chosen/cmake", "../source"]
                (build / "CMakeCache.txt").write_text(
                    "CMAKE_CACHE_MAJOR_VERSION:INTERNAL=3\nCMAKE_CACHE_MINOR_VERSION:INTERNAL=2\nCMAKE_CACHE_PATCH_VERSION:INTERNAL=3\n"
                )
                out("CMake Warning: version-specific warning")
            return ProcessOutcome(0)

    command = CommandSpec(
        shell="cmake ../source",
        cwd=str(build),
        env={
            "PATH": "child-path",
            "PTK_STEP": "configure",
            "PTK_BUILD_DIR": str(build),
            "PTK_STEP_REPORTS_DIR": str(tmp_path / "reports"),
        },
    )
    cmake.CMakeReportingRunner(Runner(), "linux").run(
        command, lambda _: None, mask=lambda text: text, on_problem=pytest.fail
    )
    [report] = cmake.read(tmp_path / "reports", "configure").cmake
    assert report.importer == "cmake-3.2" and report.version == "3.2.3"
    assert report.diagnostics[0].level == "warning"
    assert not (build / ".cmake").exists()
    assert len(commands) == 2 and command.argv is None  # authored command unchanged


def test_yaml_event_versions_and_current_append_only(tmp_path):
    from ptk.adapters.reporting.cmake_importers.common import read_events, stamp

    path = tmp_path / "CMakeFiles/CMakeConfigureLog.yaml"
    path.parent.mkdir()
    path.write_text(
        "---\nevents:\n- kind: try_compile-v1\n  description: old probe\n  buildResult: {exitCode: 1}\n...\n"
    )
    before = {str(path): stamp(path)}
    with path.open("a") as stream:
        stream.write(
            "---\nevents:\n- kind: try_compile-v1\n  description: current probe\n  buildResult: {exitCode: 0}\n- kind: try_compile-v99\n  description: unknown version\n...\n"
        )
    report = CMakeReport("configure", str(tmp_path), "3.30.9", "cmake-3.2")
    read_events(report, tmp_path, before)
    assert [c["name"] for c in report.checks] == ["current probe"]


def test_unreadable_api_keeps_console_errors_and_does_not_change_process(
    tmp_path, monkeypatch
):
    from ptk.adapters.reporting.cmake_importers import v3

    def unreadable(*args):
        raise ValueError("malformed current reply")

    monkeypatch.setattr(v3, "read_api", unreadable)
    source(tmp_path / "source")
    executable = shutil.which("cmake")
    build, reports = tmp_path / "build", tmp_path / "reports"
    command = CommandSpec(
        argv=[executable, "-S", str(tmp_path / "source"), "-B", str(build)],
        cwd=str(tmp_path),
        env={
            **os.environ,
            "PTK_BUILD_DIR": str(build),
            "PTK_STEP_REPORTS_DIR": str(reports),
            "PTK_STEP": "configure",
        },
    )
    outcome = cmake.CMakeReportingRunner(SubprocessRunner(), "linux").run(
        command, lambda _: None, mask=lambda text: text, on_problem=pytest.fail
    )
    imported = cmake.read(reports, "configure")
    assert outcome.exit_code == 0
    assert any("malformed current reply" in p for p in imported.problems)
    assert len(imported.cmake[0].diagnostics) == 3
