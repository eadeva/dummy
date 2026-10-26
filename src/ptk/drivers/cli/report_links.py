"""Report paths everywhere; browser URLs in interactive local VS Code terminals."""

from rich.markup import escape

from ...domain.errors import PtkError
from .state import console


def print_report(app, path, *, root, ci=False, logs=()):
    console.print(f"report: {escape(str(path))}", highlight=False, soft_wrap=True)
    if (
        ci
        or path.suffix.lower() != ".html"
        or not console.is_terminal
        or app.host.variables.get("TERM_PROGRAM") != "vscode"
    ):
        return
    try:
        url = app.report_url(path, root=root, logs=logs)
    except (PtkError, OSError, ValueError) as exc:
        console.print(f"[dim]browser link unavailable: {escape(str(exc))}[/]")
    else:
        console.print(f"browser: {escape(url)}", highlight=False, soft_wrap=True)
