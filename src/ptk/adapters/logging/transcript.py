"""Append-only plain text transcripts; raw per-step capture is separate."""

import threading
from datetime import datetime

from rich.text import Text

from ...domain import run_output as display
from ...domain.logging import Level


def visible(text):
    return Text.from_ansi(
        text.replace("\r\n", "\n").replace("\r", "\n")
    ).plain.expandtabs(8)


class TranscriptFile:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")
        self._lock = threading.Lock()

    def write(self, text):
        with self._lock:
            stamp = datetime.now().astimezone().strftime("%H:%M:%S")
            self._file.write(
                "".join(f"{stamp} {line}\n" for line in visible(text).split("\n"))
            )
            self._file.flush()

    def close(self):
        self._file.close()


class RunTranscript:
    def __init__(self, write, *, level=Level.DEBUG, job_label=None):
        self.write, self.level, self.job_label = write, level, job_label

    def run_started(self, plan):
        self.plan = plan
        self.label = self.job_label or plan.job
        self.identity = display.prefix(self.label, plan.variant)
        self.block(
            display.start_block(
                "JOB",
                self.identity,
                display.job_rows(plan, verbose=self.level <= Level.DEBUG),
            )
        )

    def block(self, block):
        self.write(visible(display.plain(block)))

    def record(self, text, step=None):
        tag = display.prefix(self.label, self.plan.variant, step.name if step else None)
        self.write("\n".join(f"{tag} {line}" for line in visible(text).split("\n")))

    def step_started(self, step, command):
        self.block(
            display.step_block(
                self.identity + f"[{step.name}]",
                step=step,
                command=command,
            )
        )

    def output(self, step, line):
        self.record(line, step)

    def message(self, level, text, step=None):
        if level >= self.level:
            self.record(f"{level.label}: {text}", step)

    def step_finished(self, step, result):
        self.block(display.step_block(self.identity + f"[{step.name}]", result=result))

    def run_finished(self, result):
        self.block(display.job_summary(result, self.label))
