"""Print report file paths without starting a browser or background server."""

from ...domain import run_output as display
from .state import console


def print_report(path, *, identity, kind):
    from .console import print_block

    print_block(console, display.contextual(identity, [f"report: {path}"], kind))
