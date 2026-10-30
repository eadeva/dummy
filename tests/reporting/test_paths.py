"""Report output remains a file path, with no localhost helper process."""

import io
import subprocess

import pytest
from rich.console import Console
from rich.text import Text

from ptk.drivers.cli import report_links


@pytest.mark.parametrize("kind,color_number", [("JOB", 6), ("WORKFLOW", 5)])
@pytest.mark.parametrize("terminal", [False, True])
def test_report_path_does_not_start_browser_helper(
    tmp_path, monkeypatch, kind, color_number, terminal
):
    output = io.StringIO()
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.setattr(
        report_links,
        "console",
        Console(
            file=output,
            force_terminal=terminal,
            color_system="standard" if terminal else None,
            no_color=False,
            width=200,
        ),
    )

    def unexpected(*args, **kwargs):
        raise AssertionError("printing a report path must not launch a process")

    monkeypatch.setattr(subprocess, "Popen", unexpected)
    path = tmp_path / "folder with [brackets]" / "report.html"
    report_links.print_report(path, identity="[debug][owner]", kind=kind)
    text = output.getvalue()
    rendered = Text.from_ansi(text)
    assert rendered.plain == f"[debug][owner] report: {path}\n"
    if terminal:
        owner_style = rendered.get_style_at_offset(report_links.console, 0)
        assert owner_style.bold and owner_style.color.number == color_number
        path_style = rendered.get_style_at_offset(
            report_links.console, rendered.plain.index(str(path))
        )
        assert path_style.color.is_default
    else:
        assert "\x1b" not in text
    assert "http://" not in text and "browser:" not in text
    assert not (tmp_path / ".ptk/report-viewer").exists()
