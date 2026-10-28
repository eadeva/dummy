"""Report output remains a file path, with no localhost helper process."""

import io
import subprocess

from rich.console import Console

from ptk.drivers.cli import report_links


def test_report_path_does_not_start_browser_helper(tmp_path, monkeypatch):
    output = io.StringIO()
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.setattr(
        report_links, "console", Console(file=output, force_terminal=True, width=200)
    )

    def unexpected(*args, **kwargs):
        raise AssertionError("printing a report path must not launch a process")

    monkeypatch.setattr(subprocess, "Popen", unexpected)
    path = tmp_path / "report.html"
    report_links.print_report(path)
    text = output.getvalue()
    assert str(path) in text
    assert "http://" not in text and "browser:" not in text
    assert not (tmp_path / ".ptk/report-viewer").exists()
