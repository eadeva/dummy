Declared outputs and PTK cache
==============================

Outputs belong to the project
-----------------------------

``outputs`` is a project-owned list of artifact files or folders. Its principal
purpose is to describe artifacts for **uploads and downloads in workflows**.
Keep this declaration useful independently of caching. Your workflow commands
and chosen transfer tools perform the uploads and downloads: declaring paths
neither transfers files nor generates a CX pipeline. Destination routing is
covered in :doc:`artifacts`.

PTK's built-in cache is an **optional aid** that can also use these declarations.
The project owns the cache configuration, the completeness and validity of its
outputs, and the decision that reusing them is correct. PTK does not infer a
command's inputs, inspect source dependencies, discover remote changes or
validate artifact meaning. A matching fingerprint means the declared contents
match an earlier successful execution; it does not prove a build is current.

Both steps and jobs accept:

* ``outputs: [path, ...]`` — explicit literal file or directory paths. Directories
  include their contents recursively. PTK variables are supported; globs are not
  expanded. Blank paths and duplicate declarations are rejected.
* ``cache: true`` — opt into local output reuse; default ``false``. Enabling it
  requires a nonempty ``outputs`` list. Outputs alone never enable caching.

Step paths are relative to the resolved step ``cwd`` (repository root by
default); job paths are relative to the repository root. Absolute paths are
allowed. There is **no implicit run.build_dir fallback** and no inference from
step outputs to job outputs. You can explicitly select a PTK-managed location
with ``${run.build_dir}`` on a step or ``${steps.compile.build_dir}`` on a job.
Prefer stable build artifacts over PTK log/report directories, which PTK rotates
or recreates for each invocation.

Step reuse
----------

In ``jobs/build.ptk.yml``:

.. code-block:: yaml

   steps:
     prepare:
       run: python tools/prepare.py
       outputs: [generated]
     compile:
       needs: [prepare]
       run: python tools/build.py
       outputs: [dist/application, dist/metadata.json]
       cache: true

``prepare`` always executes because it has no ``needs``. If its declared outputs
are unchanged, ``compile`` can reuse the outputs already on disk. ``prepare``
does not need ``cache: true`` to supply dependency fingerprints. The project
must ensure its declarations and commands account for every change relevant to
``compile``. For example, if the compilation also reads source files outside
``generated``, have the always-running preparation step produce a content
manifest covering those sources, or keep compilation's PTK cache disabled.

A dependent step is reused only when all of these conditions hold:

#. It opts in and declares outputs.
#. Every direct prerequisite succeeded in this invocation and declares readable
   outputs. A reused prerequisite counts as successful. A tolerated failure
   permits execution but does not permit a cache hit.
#. The dependency output contents and the consumer's resolved execution
   configuration match its saved receipt.
#. Every declared consumer output exists and still matches that receipt.

Every root step executes, including multiple roots and roots listed after their
dependents in YAML. A join checks every direct prerequisite. Reuse applies to
commands, Python commands, built-in operations (``uses``), and generator steps.
A hit skips the entire step, including its generators and environment setup.
Do not opt in a step whose external side effects must occur every time.

Workflow job reuse
------------------

Job output declarations describe the artifacts shared across job boundaries.
Whole-job reuse is configured in the project job file, not on a workflow call.
For example, ``jobs/build.ptk.yml`` can declare:

.. code-block:: yaml

   outputs: [dist/application]
   steps:
     compile:
       run: python tools/build.py

And ``jobs/package.ptk.yml``:

.. code-block:: yaml

   outputs: [dist/application.zip]
   cache: true
   steps:
     archive:
       run: python tools/package.py

In ``workflows/release.ptk.yml``:

.. code-block:: yaml

   jobs:
     build:
       job: build
     package:
       job: package
       needs: [build]

``build`` always runs. ``package`` may reuse its existing archive if all declared
build outputs, its own archive and its execution configuration match. A whole-job
hit skips all its steps, even steps without step-level caching. If the whole-job
check misses, the job runs and applies its normal step-level rules.

All workflow roots always run; "first" means no ``needs``, not YAML order.
Standalone job invocations always run the job and apply step-level rules.
Workflows spanning repositories use each producing job's resolved absolute
outputs and each consumer repository's local receipts. Variants are isolated.
Local workflows do not become CX workflows through this setting; see
:doc:`workflows` for the existing CX boundary.

For upload/download jobs, consider remote state explicitly. Local artifacts
cannot establish whether a remote upload still exists or whether a downloadable
artifact has changed. Keep transfer steps/jobs uncached when the transfer must
occur, or make the project's always-running prerequisite establish the relevant
remote state. PTK does not assume this responsibility.

Force execution
---------------

``--no-cache-ptk`` disables PTK's built-in cache throughout the invocation,
including every job and step in a workflow. It is available globally and on job
and workflow run commands and their shortcuts::

   ptk --no-cache-ptk build
   ptk build --no-cache-ptk
   ptk run build --no-cache-ptk
   ptk workflow run release --no-cache-ptk
   ptk release --no-cache-ptk

The extension exposes the same option in job/workflow parameter forms and saved
tasks. Tool-native caching (CMake, Bazel, Ninja, compiler caches and other tools)
is untouched; PTK does not add cache-related arguments to those commands.

A forced execution bypasses cache reads and output hashing, invalidates old
receipts for attempted work, and does not write new reusable receipts. A later
normal invocation establishes fresh receipts. ``--re-run`` also bypasses PTK
reuse after its normal cleanup. ``--only-step`` runs the selected step without
reuse because prerequisites were not executed. ``--to`` retains normal rules
for the selected dependency subgraph. Dry runs show configuration and eligibility
without probing, creating or invalidating receipts; they cannot promise a hit
before prerequisites execute.

GUI jobs cannot enable whole-job caching, and their final detached launch step
cannot enable caching. Eligible preparation steps may use the cache, but opening
the GUI always launches the program.

Storage, matching and reports
-----------------------------

PTK stores only small versioned receipts in ``.ptk/output-cache/v1`` beneath each
consumer repository. They contain hashes and the original successful run ID;
there are **no artifact copies, downloads or restoration operations**. Remove
this directory to reset PTK caching. Deleting or changing an output causes a miss
and normal execution, not restoration. Cleanup does not gain permission to
delete arbitrary declared paths outside its existing managed directories.

File bytes, directory entry names and file modes are fingerprinted. File mtime
alone is ignored, so touching a file or regenerating identical contents does not
force dependent execution. Missing, unreadable, symbolic-link or special-file
outputs are misses. Files changing during hashing also cause a miss. Hashing
large directories has a cost; declare meaningful artifacts and avoid overly
broad trees. External processes and concurrent unrelated jobs still need project
coordination; PTK does not lock or sandbox arbitrary output paths.

Keys include PTK/platform/repository/job/variant identity, resolved parameters,
features and relevant execution settings, environment and secrets. Secret values
are hashed and are never stored in receipts. Per-invocation PTK run IDs and the
generated version-file location are excluded from the inherited environment key;
explicit run-specific substitutions in commands or declarations still change
the key. Files containing scripts, undeclared inputs and remote state are not
implicitly hashed. A changed producer command that emits identical declared
contents need not invalidate its dependent.

Only successful attempts can populate receipts; a new attempt invalidates its
old receipt before execution. Failed or cancelled work cannot fall back to its
old outputs as a cache hit. Cache storage errors warn and fall back to execution.
Caching is not a substitute for meaningful exit statuses or project validation.

Console summaries, JSON, Markdown, HTML, timelines and dependency graphs identify
**Reused** work and its original run ID. A reused step has zero attempts, no new
exit code and no command log. JSON keeps ``status: passed`` for dependency success
and records ``reused_from`` to distinguish reuse from execution. JUnit represents
reused steps as skipped, never as newly passed tests. Previous test results and
diagnostics are not replayed as new evidence; consult the original run for that
evidence. Normal log-retention rules still apply. A fresh full report and separate
diagnostics report are generated for the invocation; existing local error-opening
rules remain in effect.

The extension's configuration form repeats the ownership guidance for both jobs
and steps, including before caching is enabled. Field help documents path bases,
opt-in requirements and the execution-wide bypass. See :doc:`editor`,
:doc:`reports`, :need:`REQ_Sw_OUTPUT_REUSE` and :need:`DD_OUTPUT_REUSE`.
