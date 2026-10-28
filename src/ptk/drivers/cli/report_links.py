"""Print report file paths without starting a browser or background server."""

from rich.markup import escape

from .state import console


def print_report(path):
    console.print(f"report: {escape(str(path))}", highlight=False, soft_wrap=True)
