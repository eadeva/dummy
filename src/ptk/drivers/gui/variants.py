"""Tk desktop variant YAML editor, loaded only on explicit GUI invocation."""

from pathlib import Path

from ...adapters.variant_editor import save_edit
from ...application.use_cases.variant_editor import VariantEditorSession
from ...domain.errors import PtkError
from ...domain.variants.rules import resolve


def open_editor(session: VariantEditorSession, output: Path) -> None:
    initial = session.initial_text()
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk
    except ImportError:
        raise PtkError(
            "The tkinter editor needs Python with Tk support (python3-tk on Linux). "
            "Use a desktop session or choose --plugin NAME."
        ) from None
    try:
        root = tk.Tk()
    except tk.TclError:
        raise PtkError(
            "The variant editor requires a graphical desktop and working Tk display."
        ) from None
    root.title(f"ptk — {session.config.project.name} — variants")
    root.geometry("1000x760")
    root.minsize(640, 480)
    ttk.Label(
        root,
        text="Edit the product-line YAML: components, features, variants and constraints.",
        padding=10,
    ).pack(anchor="w")
    editor = scrolledtext.ScrolledText(root, wrap="none", undo=True, height=26)
    editor.pack(fill="both", expand=True, padx=10)
    editor.insert("1.0", initial)
    preview = scrolledtext.ScrolledText(root, height=8, wrap="word", state="disabled")
    preview.pack(fill="x", padx=10, pady=8)
    ttk.Label(
        root,
        text=f"Export a standalone project to: {output}\n"
        "Includes and comments are flattened. Original files are preserved.",
        padding=10,
    ).pack(anchor="w")

    def validate():
        try:
            config = session.validate(editor.get("1.0", "end-1c"))
            lines = []
            for name in config.variants.buildable():
                variant = resolve(config.variants, name)
                lines.append(f"{name}: {variant.values}")
                lines.extend(str(i) for i in variant.warnings)
            message = "Valid configuration\n" + "\n".join(lines)
        except PtkError as exc:
            message = str(exc)
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        preview.insert("1.0", message)
        preview.configure(state="disabled")

    def save():
        try:
            save_edit(session, editor.get("1.0", "end-1c"), output)
        except PtkError as exc:
            messagebox.showerror("Cannot export", str(exc), parent=root)
            return
        messagebox.showinfo(
            "Exported",
            f"Created {output}\nUse ptk --config FILE variant check.",
            parent=root,
        )
        root.destroy()

    def close():
        if editor.get("1.0", "end-1c") != initial and not messagebox.askyesno(
            "Discard edits?", "Close without exporting your changes?", parent=root
        ):
            return
        root.destroy()

    buttons = ttk.Frame(root, padding=10)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="Validate / preview", command=validate).pack(side="left")
    ttk.Button(buttons, text="Export validated project", command=save).pack(
        side="left", padx=10
    )
    ttk.Button(buttons, text="Close", command=close).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", close)
    validate()
    root.mainloop()
