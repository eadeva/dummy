"""Exercise workflow report opening without launching real browsers in tests."""

import pytest

from ptk.adapters import help_html


@pytest.fixture(autouse=True)
def opened_reports(monkeypatch):
    opened = []

    def open_browser(path):
        assert path.is_file()
        assert "</html>" in path.read_text(encoding="utf-8")
        opened.append(path)
        return True

    monkeypatch.setattr(help_html, "open_in_browser", open_browser)
    return opened
