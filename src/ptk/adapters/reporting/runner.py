"""Compose the shipped build-tool collectors around one process execution."""

from .bazel import BazelReportingRunner
from .cmake import CMakeReportingRunner
from .gn import GNReportingRunner


class ReportingRunner:
    def __init__(self, runner, os_name):
        self.bazel = BazelReportingRunner(runner, os_name)
        self.cmake = CMakeReportingRunner(runner, os_name)
        self.gn = GNReportingRunner(runner, os_name)

    def run(self, command, on_output, cancel=None, *, mask, on_problem):
        def execute_cmake(command, output, cancel):
            return self.cmake.run(
                command, output, cancel, mask=mask, on_problem=on_problem
            )

        def execute(command, output, cancel):
            return self.gn.run(
                command,
                output,
                cancel,
                mask=mask,
                on_problem=on_problem,
                execute=execute_cmake,
            )

        return self.bazel.run(
            command,
            on_output,
            cancel,
            mask=mask,
            on_problem=on_problem,
            execute=execute,
        )
