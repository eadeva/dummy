"""Real Tk event-loop integration; run under xvfb-run in Linux CI."""

import os

import pytest
import yaml

from ptk.application.use_cases.variant_editor import VariantEditorSession
from ptk.domain.config.model import PtkConfig
from ptk.drivers.gui.variants import open_editor

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="requires a display (xvfb-run)"
)


def test_real_editor_validation_and_export(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    monkeypatch.setattr(tk, "Tk", lambda: root)
    errors, infos, failures = [], [], []
    monkeypatch.setattr(
        messagebox, "showerror", lambda *args, **kw: errors.append(args)
    )
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kw: infos.append(args))
    session = VariantEditorSession(
        PtkConfig.model_validate(
            {"project": {"name": "GUI test"}, "variants": {"variants": {"demo": {}}}}
        )
    )
    target = tmp_path / "export.ptk.yml"

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def interact():
        try:
            widgets = list(descendants(root))
            editor = next(
                w
                for w in widgets
                if isinstance(w, tk.Text) and str(w.cget("state")) == "normal"
            )
            buttons = {w.cget("text"): w for w in widgets if isinstance(w, ttk.Button)}
            assert editor.winfo_width() > 400 and editor.winfo_height() > 100
            assert set(buttons) == {
                "Validate / preview",
                "Export validated project",
                "Close",
            }
            initial = editor.get("1.0", "end-1c")
            editor.delete("1.0", "end")
            editor.insert("1.0", "variants: [invalid]")
            buttons["Validate / preview"].invoke()
            buttons["Export validated project"].invoke()
            assert errors and not target.exists()
            editor.delete("1.0", "end")
            editor.insert("1.0", initial)
            buttons["Export validated project"].invoke()
            assert infos and target.exists()
        except BaseException as exc:  # noqa: BLE001 - propagate Tk callback failures to pytest
            failures.append(exc)
            root.destroy()

    root.after(150, interact)
    root.after(
        10000,
        lambda: (failures.append(AssertionError("GUI timed out")), root.destroy()),
    )
    open_editor(session, target)
    if failures:
        raise failures[0]
    assert yaml.safe_load(target.read_text())["variants"]["variants"] == {"demo": {}}
