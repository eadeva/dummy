"""Result identity and colors remain clear in complete, concurrent summaries."""

import io
import threading
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console

from ptk.adapters.logging.transcript import RunTranscript, TranscriptFile
from ptk.domain import run_output as display
from ptk.domain.execution.model import JobPlan, RunResult, Status, StepResult
from ptk.drivers.cli.console import ConsoleObserver, render_block
from tests.test_console_output import step


def result(steps, *, variant="debug", status=Status.PASSED):
    return RunResult(
        "demo",
        "build",
        variant,
        "run-123",
        status,
        "",
        2.5,
        {},
        {},
        steps,
        log_file=f"/logs/{variant}/build/run.log",
    )


def test_summary_colors_distinguish_identity_outcome_and_allowed_failure():
    run = result(
        [
            StepResult(("compile",), "compile", "run", Status.PASSED, duration=1.5),
            StepResult(
                ("test",),
                "test",
                "run",
                Status.FAILED,
                duration=1,
                allowed_failure=True,
                message="exit code 2",
            ),
            StepResult(
                ("package",),
                "package",
                "run",
                Status.SKIPPED,
                message="condition false",
            ),
        ]
    )
    console = Console(file=io.StringIO(), force_terminal=True, color_system="standard")
    text = render_block(display.job_summary(run, "build"))
    assert "JOB SUMMARY [debug][build] | PASSED | 2.5s" in text.plain
    assert (
        "What failed: [debug][build][test] | FAILED | allowed failure | exit code 2"
        in text.plain
    )
    assert "condition false" in text.plain

    def style(needle):
        return text.get_style_at_offset(console, text.plain.index(needle))

    assert style("JOB SUMMARY").color.name == "cyan"
    assert style("compile").color.name == "blue"
    assert style("PASSED").color.name == "green"
    assert style("FAILED").color.name == "red"
    assert style("SKIPPED").color.name == "bright_black"
    assert style("allowed failure").color.name == "yellow"
    assert style("1 failed").color.name == "red"
    assert style("0 cancelled").dim and style("0 cancelled").color is None


def test_cancelled_summary_keeps_reason_and_zero_failures_neutral():
    run = result(
        [
            StepResult(
                ("compile",),
                "compile",
                "run",
                Status.CANCELLED,
                duration=2.5,
                message="cancelled by user",
            ),
        ],
        status=Status.CANCELLED,
    )
    console = Console(file=io.StringIO())
    text = render_block(display.job_summary(run, "build"))
    assert "JOB SUMMARY [debug][build] | CANCELLED | 2.5s" in text.plain
    assert "cancelled by user" in text.plain
    assert "What failed" not in text.plain
    assert (
        text.get_style_at_offset(console, text.plain.index("CANCELLED")).color.name
        == "yellow"
    )
    assert text.get_style_at_offset(console, text.plain.index("0 failed")).dim


def test_parallel_headers_and_summaries_are_whole_blocks_with_their_own_variant(
    tmp_path,
):
    stream = io.StringIO()
    console = Console(file=stream, width=35, color_system=None, force_terminal=False)
    transcript = TranscriptFile(tmp_path / "combined.log")
    ready = threading.Barrier(2)

    def run(variant):
        observers = [ConsoleObserver(console), RunTranscript(transcript.write)]
        plan = JobPlan("demo", "build", variant, "run-123", {}, {}, [step()], {}, {})
        for observer in observers:
            observer.run_started(plan)
        ready.wait(timeout=5)
        for index in range(25):
            for observer in observers:
                observer.output(step(), f"tool line {index}")
        run_result = result(
            [
                StepResult(
                    (variant + "-compile",), variant + "-compile", "run", Status.PASSED
                ),
            ],
            variant=variant,
        )
        for observer in observers:
            observer.run_finished(run_result)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run, ["debug", "release"]))
    finally:
        transcript.close()
    logged = "\n".join(
        line.split(" ", 1)[1]
        for line in (tmp_path / "combined.log").read_text().splitlines()
    )
    for output in (stream.getvalue(), logged):
        for variant, other in [("debug", "release"), ("release", "debug")]:
            identity = f"[{variant}][build]"
            header = output.split(f"JOB {identity} | START", 1)[1].split(
                f"{identity} Run:", 1
            )[0]
            assert f"{identity} Project: demo" in header
            assert f"[{other}]" not in header
            summary = output.split(f"JOB SUMMARY {identity} | PASSED", 1)[1].split(
                f"{identity} Log:", 1
            )[0]
            assert variant + "-compile" in summary
            assert f"{identity} Steps: 1 passed | 0 failed" in summary
            assert other not in summary and "tool line" not in summary
