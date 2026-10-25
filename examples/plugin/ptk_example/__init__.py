"""Minimal repeatable, cooperative PTK extension."""


def check(step, out, ctx):
    if ctx.cancel is not None and ctx.cancel.is_set():
        return 1
    out("Example check passed")
    return 0
