"""Console identities and tool indentation survive presentation and concurrency."""

import io
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from rich.console import Console

from ptk.domain.config.model import StepSpec
from ptk.domain.execution.model import JobPlan, PlannedStep, Status, StepResult
from ptk.domain.logging import Level
from ptk.drivers.cli.console import ConsoleObserver
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def observer(stream, job="docs", variant=None, **kwargs):
    console = Console(file=stream, width=30, force_terminal=False, color_system=None)
    result = ConsoleObserver(console, **kwargs)
    result.run_started(JobPlan("demo", job, variant, "run", {}, {}, [], {}, {}))
    stream.seek(0)
    stream.truncate()
    return result


def step(name="sphinx"):
    return PlannedStep((name,), StepSpec(uses="echo"))


@pytest.mark.parametrize("variant,shown", [(None, "default"), ("debug", "debug")])
def test_step_lifecycle_and_messages_share_the_full_context(variant, shown):
    stream = io.StringIO()
    out = observer(stream, variant=variant)
    item = step()
    out.step_started(item, "sphinx-build docs output")
    out.output(item, "building [html] :smile:")
    out.message(Level.WARNING, "first\n  second", item)
    out.step_finished(
        item,
        StepResult(
            item.path,
            item.name,
            item.kind,
            Status.FAILED,
            duration=1.2,
            message="exit code 2",
            allowed_failure=True,
        ),
    )
    lines = stream.getvalue().splitlines()
    prefix = f"[docs][{shown}][sphinx] "
    assert all(line.startswith(prefix) for line in lines)
    assert [line[len(prefix) :] for line in lines] == [
        "--- STEP | START ---",
        "Command: sphinx-build docs output",
        "building [html] :smile:",
        "warning: first",
        "  second",
        "--- STEP | FAILED | 1.2s | allowed failure ---",
        "exit code 2",
    ]


def test_multiline_output_expands_tabs_before_prefix_and_cannot_move_the_cursor():
    stream = io.StringIO()
    out = observer(stream)
    for name in ["short", "much-longer-step"]:
        out.output(step(name), "\tindented\r\n  next\n\n\x1b[2K\r\x1b[31mERROR\x1b[0m")
    lines = stream.getvalue().splitlines()
    for name in ["short", "much-longer-step"]:
        prefix = f"[docs][default][{name}] "
        assert [line[len(prefix) :] for line in lines if line.startswith(prefix)] == [
            "        indented",
            "  next",
            "",
            "",
            "ERROR",
        ]
    assert "\x1b" not in stream.getvalue() and "\r" not in stream.getvalue()


def test_quiet_output_keeps_context_for_warnings_and_skipped_steps():
    stream = io.StringIO()
    out = observer(stream, quiet=True, level=Level.WARNING)
    out.output(step(), "not shown")
    out.message(Level.INFO, "not shown", step())
    out.message(Level.WARNING, "step warning", step())
    out.message(Level.WARNING, "job warning")
    out.step_finished(
        step(),
        StepResult(
            ("sphinx",), "sphinx", "uses", Status.SKIPPED, message="condition false"
        ),
    )
    assert stream.getvalue().splitlines() == [
        "[docs][default][sphinx] warning: step warning",
        "[docs][default] warning: job warning",
        "[docs][default][sphinx] --- STEP | SKIPPED | 0.0s ---",
        "[docs][default][sphinx] condition false",
    ]


def test_parallel_observers_keep_their_job_and_variant_on_every_line():
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None)
    observers = []
    for job, variant in [("docs", "debug"), ("check", "release")]:
        out = ConsoleObserver(console)
        out.run_started(JobPlan("demo", job, variant, "run", {}, {}, [], {}, {}))
        observers.append(out)
    stream.seek(0)
    stream.truncate()

    def emit(out):
        for index in range(20):
            out.output(step(), f"first {index}\n  second {index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(emit, observers))
    for job, variant in [("docs", "debug"), ("check", "release")]:
        prefix = f"[{job}][{variant}][sphinx] "
        assert [
            line[len(prefix) :]
            for line in stream.getvalue().splitlines()
            if line.startswith(prefix)
        ] == [
            line
            for index in range(20)
            for line in [f"first {index}", f"  second {index}"]
        ]


def test_real_command_output_is_normalized_only_for_the_console(tmp_path):
    payload = "\tindented\r\nprogress 1\r\x1b[2Kprogress 2\n[red] :smile:\n"
    write_project(
        tmp_path / ".main.ptk.yml",
        {
            "project": {"name": "demo"},
            "report_formats": [],
            "variants": {"default": "debug", "variants": {"debug": {}}},
            "jobs": {
                "docs": {
                    "steps": {
                        "sphinx": {
                            "run": [
                                sys.executable,
                                "-c",
                                f"import sys; sys.stdout.buffer.write({payload.encode()!r})",
                            ],
                        }
                    }
                }
            },
        },
    )
    result = CliRunner().invoke(cli, ["docs"], cwd=tmp_path, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    for text in ["        indented", "progress 1", "progress 2", "[red] :smile:"]:
        assert f"[docs][debug][sphinx] {text}\n" in result.output
    captured = (tmp_path / "_logs/debug/docs/steps/sphinx.log").read_bytes()
    assert b"progress 1\r\x1b[2Kprogress 2" in captured
    assert b"\tindented" in captured
    assert b"[docs][debug][sphinx]" not in captured


@pytest.mark.parametrize("verbose", [False, True])
def test_headers_use_prepared_metadata_and_only_verbose_shows_features(verbose):
    stream = io.StringIO()
    out = ConsoleObserver(
        Console(file=stream, width=90, color_system=None),
        level=Level.DEBUG if verbose else Level.INFO,
    )
    plan = JobPlan(
        "Firmware",
        "docs",
        "debug",
        "run-123",
        {},
        {},
        [step()],
        {},
        {},
        report_context={
            "repository_alias": "fw",
            "ptk_version": "9.0.0",
            "versions": {"projects": {"fw": {"value": "2.4.1"}}},
            "variant": {
                "description": "Development",
                "chain": ["base", "debug"],
                "components": ["core"],
                "features": {"core.MODE": "safe"},
            },
        },
    )
    out.run_started(plan)
    text = stream.getvalue()
    assert "JOB docs | START" in text
    assert "Project: Firmware | Project version: 2.4.1" in text
    assert "Repository: fw | PTK: 9.0.0" in text
    assert "Variant: debug — Development" in text
    assert "Components: 1 | Resolved features: 1" in text
    assert ("core.MODE" in text) is verbose
    assert ("Inheritance: base → debug" in text) is verbose
    assert "\x1b" not in text


def test_header_entity_colors_are_distinct_from_result_colors():
    from ptk.drivers.cli.console import header

    stream = io.StringIO()
    console = Console(
        file=stream, force_terminal=True, no_color=False, color_system="standard"
    )
    header(console, "WORKFLOW", "verify", "START")
    out = ConsoleObserver(console)
    out.run_started(JobPlan("demo", "docs", None, "run", {}, {}, [], {}, {}))
    out.step_started(step(), "echo hello")
    out.step_finished(step(), StepResult(("sphinx",), "sphinx", "uses", Status.FAILED))
    text = stream.getvalue()
    assert "\x1b[1;35m======== WORKFLOW" in text
    assert "\x1b[1;36m-------- JOB" in text
    assert "\x1b[1;34m--- STEP" in text
    assert "\x1b[1;31mFAILED" in text
