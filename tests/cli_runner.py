"""Click's runner with an explicit working directory, as used by real PTK calls."""

from contextlib import chdir, nullcontext

from click.testing import CliRunner as ClickRunner


class CliRunner(ClickRunner):
    def invoke(self, cli, args=None, *, cwd=None, **kwargs):
        with chdir(cwd) if cwd is not None else nullcontext():
            return super().invoke(cli, args, **kwargs)
