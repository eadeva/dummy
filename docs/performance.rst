CLI startup performance
=======================

Help must reflect current jobs, workflows and maintainer permissions. PTK loads
and validates configuration for that invocation; no persistent help cache can
hide a recent edit or keep an obsolete permission.

Measured improvement
--------------------

Fresh Python processes on the same Linux x86-64 host, Python 3.12.14, seven
measured samples after one warmup per case. Filesystem caches were warm; output
was redirected at a fixed 100-column width with the normal user role. These
measurements include Python startup and rendering, but exclude any initial
``uv run`` synchronization or installer wrapper. They are not cold-disk timings
or a prediction of a particular developer's Windows machine.

The baseline is commit ``f7be8c1``. Raw samples and host metadata are recorded in
the source checkout under ``docs/benchmarks/cli-before.json`` and
``docs/benchmarks/cli-after.json``.

.. list-table:: Median wall time
   :header-rows: 1
   :widths: 43 19 19 19

   * - Scenario
     - Before
     - After
     - Reduction
   * - ``version``
     - 331 ms
     - 235 ms
     - 29%
   * - ``no-project-help``
     - 341 ms
     - 254 ms
     - 26%
   * - ``ptk-project-help``
     - 380 ms
     - 259 ms
     - 32%
   * - ``ptk-setup-help``
     - 367 ms
     - 251 ms
     - 31%
   * - ``ptk-job-help``
     - 376 ms
     - 250 ms
     - 34%
   * - ``broken-project-help``
     - 454 ms
     - 237 ms
     - 48%
   * - ``vmr-20-help``
     - 1001 ms
     - 383 ms
     - 62%
   * - ``vmr-20-member-help``
     - 384 ms
     - 246 ms
     - 36%
   * - ``vmr-100-help``
     - 3648 ms
     - 987 ms
     - 73%
   * - ``vmr-100-member-help``
     - 391 ms
     - 301 ms
     - 23%

Each generated VMR member has twelve jobs in separate YAML fragments, two variants
and one workflow. The 20-member and 100-member cases include all qualified workflow
shortcuts in root help. Member help still loads only the selected repository's
full configuration, while reading the workspace metadata needed for routing.
Root help remains proportional to the amount of configuration across members;
retaining all workflow shortcuts requires inspecting those configurations.

What changed
------------

* Compute diagnostic filenames once per YAML file, preserving individual line
  locations. The baseline 100-member profile recomputed paths about 80,000 times.
* Use PyYAML's C safe parser when available, with the Python safe parser as a
  fallback. Both backends are tested for includes, custom tags, merge keys,
  duplicate keys and error locations.
* Load/configure each CLI project and resolve its role once per invocation.
  Cache expected failures too, so broken or absent configuration is not repeatedly
  searched and parsed while rendering help. A new invocation rereads everything.
* Defer execution, installer, Python runtime, vault and reporting services and
  their imports until used. Ordinary help avoids those modules. Explicitly
  configured plugins still load and validate, and can contribute their own cost.

Run the benchmark
-----------------

In a PTK source checkout with its Python environment installed::

   uv run python scripts/benchmark_cli.py --output .ptk/benchmark-cli.json

The script starts a new Python process for every sample, creates its fixtures in
a temporary directory, runs only help/version commands, and reports medians,
nearest-rank p95 and raw samples. With seven samples, p95 is the slowest sample;
use more rounds for useful tail estimates. It never runs jobs or installs tools.
For a longer run or selected cases::

   uv run python scripts/benchmark_cli.py --rounds 20 --vmr-sizes 20 100 --output .ptk/benchmark-cli.json
   uv run python scripts/benchmark_cli.py --scenario ptk-project-help --rounds 20 --output .ptk/help-benchmark.json

Run before/after measurements sequentially on the same machine and interpreter,
without concurrent tests or builds. Keep the fixture sizes and terminal settings
the same. Linux and Windows CI print benchmark results after the Python 3.12 tests;
there are no wall-time assertions on shared runners.

Profile an installed environment
--------------------------------

Use the Python environment containing PTK and the repository where help is slow::

   python -m cProfile -o ptk-help.prof -m ptk --help
   python -c "import pstats; pstats.Stats('ptk-help.prof').strip_dirs().sort_stats('cumulative').print_stats(30)"
   python -X importtime -m ptk --help

Profiling adds overhead: use it to identify expensive work, not to claim wall-time
speedups. Compare workspace-root help with ``ptk ALIAS --help`` and explicit
``ptk -c PATH/TO/.main.ptk.yml --help`` to separate workspace configuration cost
from base startup. Record PTK/Python versions, OS, repository count, config size
and selected plugins. Keep profiles local; they contain source and project paths.
