"""Repeatable CLI startup benchmarks; each sample starts a fresh Python process.

Run with the Python environment containing PTK. Fixtures are temporary and only
help/version commands are executed. No job, tool installation or network access.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def write_project(root: Path, alias: str, *, jobs: int = 12) -> None:
    config = root / "config"
    config.mkdir(parents=True)
    (root / ".main.ptk.yml").write_text(
        f"repository: {{alias: {alias}, config_path: config}}\n", encoding="utf-8"
    )
    (config / "project.ptk.yml").write_text(f"name: {alias}\n", encoding="utf-8")
    for directory in ("jobs", "variants", "workflows"):
        (config / directory).mkdir()
    for name in ("debug", "release"):
        (config / "variants" / f"{name}.ptk.yml").write_text("{}\n", encoding="utf-8")
    for i in range(jobs):
        (config / "jobs" / f"job-{i}.ptk.yml").write_text(
            f"help: Benchmark job {i}\n"
            "params: {mode: {default: debug}, count: {type: int, default: 2}}\n"
            "steps:\n  - inspect: {uses: echo, with: {message: '${params.mode}'}}\n"
            "  - finish: {uses: echo, with: {message: done}}\n",
            encoding="utf-8",
        )
    (config / "workflows/verify.ptk.yml").write_text(
        "steps: [{check: {job: job-0}}, {test: {job: job-1}}]\n", encoding="utf-8"
    )


def scenarios(temporary: Path, repo: Path, sizes: list[int]):
    empty = temporary / "empty"
    empty.mkdir()
    yield "version", empty, ["--version"]
    yield "no-project-help", empty, ["--help"]
    yield "ptk-project-help", repo, ["--help"]
    yield "ptk-setup-help", repo, ["setup", "--help"]
    yield "ptk-job-help", repo, ["test", "--help"]
    broken = temporary / "broken"
    broken.mkdir()
    (broken / ".main.ptk.yml").write_text(
        "repository: {alias: broken, config_path: .}\nunknown: true\n",
        encoding="utf-8",
    )
    yield "broken-project-help", broken, ["--help"]
    for size in sizes:
        root = temporary / f"vmr-{size}"
        root.mkdir()
        members = [f"repo-{i:03}" for i in range(size)]
        (root / ".main.ptk.yml").write_text(
            "virtual_monorepo: true\nmembers: " + json.dumps(members) + "\n",
            encoding="utf-8",
        )
        for alias in members:
            write_project(root / alias, alias)
        yield f"vmr-{size}-help", root, ["--help"]
        yield f"vmr-{size}-member-help", root, [members[0], "--help"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--vmr-sizes", type=int, nargs="+", default=[20, 100])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="working-tree")
    parser.add_argument(
        "--scenario", action="append", help="Run only these named scenarios."
    )
    args = parser.parse_args()
    if args.rounds < 1 or args.warmups < 0 or any(n < 1 for n in args.vmr_sizes):
        parser.error(
            "rounds and VMR sizes must be positive; warmups must be nonnegative"
        )
    repo = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PTK_ROLE": "user",
        "PTK_CI": "0",
        "NO_COLOR": "1",
        "COLUMNS": "100",
    }
    result = {
        "label": args.label,
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "rounds": args.rounds,
        "warmups": args.warmups,
        "method": "fresh Python processes; warm filesystem caches; redirected help; user role",
        "scenarios": {},
    }
    with tempfile.TemporaryDirectory(prefix="ptk-benchmark-") as folder:
        for name, cwd, options in scenarios(Path(folder), repo, args.vmr_sizes):
            if args.scenario and name not in args.scenario:
                continue
            samples = []
            for index in range(args.warmups + args.rounds):
                start = time.perf_counter()
                completed = subprocess.run(
                    [sys.executable, "-m", "ptk", *options],
                    check=False,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120,
                )
                elapsed = (time.perf_counter() - start) * 1000
                if completed.returncode:
                    raise RuntimeError(f"{name} failed: {completed.stderr}")
                if index >= args.warmups:
                    samples.append(elapsed)
            stats = {
                "median_ms": statistics.median(samples),
                "min_ms": min(samples),
                "p95_ms": sorted(samples)[math.ceil(0.95 * len(samples)) - 1],
                "samples_ms": samples,
            }
            result["scenarios"][name] = stats
            print(
                f"{name:28} median {stats['median_ms']:9.1f} ms   p95 {stats['p95_ms']:9.1f} ms",
                flush=True,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )


if __name__ == "__main__":
    main()
