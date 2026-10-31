Artifactory destinations
========================

PTK resolves **where** artifacts belong. GitHub workflows choose files, supply
credentials and perform uploads. Resolution does not run the producing job,
install tools, request credentials, create version files or contact Artifactory.
Configured version sources are discovered normally, including command sources.

Configuration
-------------

Place ``artifactory_paths.ptk.yml`` directly in ``repository.config_path``.
It contains the destination body without an ``artifactory`` wrapper and owns all
artifact routes. Explicit CLI overrides remain available for inspection.

.. literalinclude:: ../../examples/artifacts/config/artifactory_paths.ptk.yml
   :language: yaml

The destination is ``url / repository / base_path / event.path / job.path``.
An event can override the repository. The ``push`` event accepts either a common
``path`` or ``branch``/``tag`` routes selected by ``GITHUB_REF_TYPE``; each selected
route can also override the repository. Other events use a single path.
An omitted job entry adds no suffix. Unknown events, missing push routes, unknown
jobs and unresolved values are errors. Job visibility and ``command_audience.artifacts``
apply to the command. Job suffix names refer to PTK jobs, not GitHub job IDs.

Branch slashes are retained. Paths are relative, with no ``.``/``..``, empty
interior segments, backslashes or control characters. The returned ``path`` is
unencoded; the HTTPS ``url`` encodes each segment and ends in ``/``. Credentials,
queries and fragments are not accepted in the server URL. No file glob, upload
policy or credentials section belongs in this configuration.

Placeholders
------------

``${project.alias}`` identifies the selected repository, including VMR members.
``${run.job}`` and ``${run.variant}`` identify the requested job and resolved
variant; projects without variants use ``default``. ``${version.current.value}``
refers to the current repository's discovered version; explicit dependencies
remain accessible through ``${version.projects.ALIAS.*}``.

``${version.current.sort_key}`` projects numeric major/minor/patch into four-digit
components: ``1.2.3`` becomes ``0001_0002_0003``. It is available for parsed semantic
versions whose components are at most 9999. It orders numeric release components,
not prerelease identifiers; ``rc``/``beta`` and build metadata have no additional
ordering rule. Unparsed versions and larger components have no sort key and
cannot use a template requiring it. Version values themselves are unchanged.

``${date.timestamp}`` provides local invocation time as ``2026_10_26_1507``;
``${date.utc.timestamp}`` uses UTC. These values are captured once, rather than
changing during resolution. See :doc:`/guides/configuration` for date components and
custom combinations. ``${vars.*}`` can reuse ordinary configuration variables.
Environment references such as ``${env:ARTIFACTORY_URL}`` use the invoking
environment, including when nested in variables.

The destination-only ``github`` namespace reads runner metadata, not arbitrary
GitHub expressions. Available fields are ``event_name``, ``ref_type``, ``ref_name``,
``sha``, ``run_id``, ``run_attempt`` and ``repository``; the event file supplies
``event.pull_request.number``, ``event.release.tag_name`` and
``event.release.prerelease``. Missing fields fail only when the selected template
uses them. PTK does not evaluate ``${{ ... }}`` GitHub expressions in this file.

CLI and workflow outputs
------------------------

Resolve JSON, GitHub step-output lines or just the URL::

   ptk -V default maintainer artifacts destination --job package
   ptk maintainer artifacts destination --job package --format github
   ptk maintainer artifacts destination --job package --format url

JSON and GitHub formats contain ``url``, ``repository`` and ``path``. GitHub output
is printed to stdout; the workflow explicitly appends it to its output file:

.. code-block:: yaml

   - name: Resolve upload destination
     id: destination
     run: ptk maintainer artifacts destination --job package --format github >> "$GITHUB_OUTPUT"

Subsequent workflow steps can read ``steps.destination.outputs.url`` or ``path``.
Keep authentication and actual uploading in those steps. This example uses a
Generic repository; package-specific repositories still require their appropriate
publication protocol and metadata. Event activity filters such as
``release: {types: [published]}`` belong in the GitHub workflow.

From a VMR root select the repository explicitly, for example
``ptk firmware maintainer artifacts destination --job package``. Each member owns its rules,
alias, variants and version sources. No project settings or tool environments
are merged across members.

Local preview works without GitHub or network access. To try the bundled sample,
copy ``examples/artifacts`` outside this Git checkout and open a terminal in it::

   ptk maintainer artifacts destination --job package --event release
   ptk maintainer artifacts destination --job package --event release --at 2026-10-26T15:07:00+01:00

``--event`` overrides the detected event for routing. ``--at`` accepts a
timezone-aware ISO timestamp and fixes all date placeholders for this resolution.
Use the same value across separate invocations when they must share a timestamp;
otherwise each invocation has its own current time. Other preview context comes
from the usual ``GITHUB_*`` variables and ``GITHUB_EVENT_PATH``.

Declared artifact outputs
-------------------------

Jobs and steps can declare ``outputs`` as a list of files or folders. These
project-owned declarations primarily describe artifacts for workflow uploads and
downloads; the workflow's transfer commands remain responsible for moving them.
They do not replace the destination rules above or automatically transfer files.
PTK's optional built-in cache can also use explicit outputs when ``cache: true``.
Cache configuration and correctness remain the project's responsibility. See
:doc:`output-reuse` for paths, ownership, workflow reuse and ``--no-cache-ptk``.

Use :doc:`cx-matrix` in a GitHub setup job to export eligible variant/job pairs,
version/source commit, per-job destinations and the shared upload base
in one invocation. It is available in CX without human maintainer identity.

Completed-job upload configuration
----------------------------------

After each actual job execution PTK writes ``upload.json`` alongside ``run.json``
in that job's log directory, normally ``_logs/VARIANT/JOB/upload.json``. Custom
layouts apply. The execution summary prints declared output paths, their producer
and availability, and the configuration file location. JSON, HTML and Markdown
reports retain this information; workflow reports retain each child's manifest.
Dry runs do not generate this file. A job with no available outputs gets an
empty ``files`` list, so an uploader can skip it.

This is a **PTK upload manifest**, not a JFrog CLI File Spec. A workflow uploader
reads it and supplies the destination exported by the setup matrix. Keeping the
destination separate preserves the first job's timestamped upload base. PTK does
not perform a transfer or write credentials into the manifest.

String outputs remain valid. To distinguish artifacts from one step, add an
optional literal ``artifact_type`` to that output's declaration:

.. code-block:: yaml

   steps:
     compile:
       run: python ci/build.py
       outputs:
         - path: dist/application.bin
           artifact_type: binaries
         - path: dist/application.map
           artifact_type: symbols
         - dist/build-info.json

``path`` has the same substitutions and relative-path rules as a string output.
``artifact_type`` is optional metadata, not inferred from the filename. The
same form works on job outputs and with the optional PTK cache. Path ownership
and cache correctness remain the project's responsibility.

For example, the completed run can produce:

.. code-block:: json

   {
     "schema_version": 1,
     "run_id": "20261031-150000-example",
     "repository": "firmware",
     "files": [{
       "path": "/workspace/firmware/dist/application.bin",
       "kind": "file",
       "properties": {
         "version": "1.2.3",
         "commit": "0123456789abcdef0123456789abcdef01234567",
         "variant_alias": ["debug", "dev"],
         "job": "build",
         "step": "compile",
         "artifact_type": "binaries"
       }
     }]
   }

``path`` is an absolute, literal local path; ``kind`` is ``file`` or ``directory``.
The uploader decides how to package or walk directories. ``variant_alias``
includes the canonical variant and all configured aliases, or ``["default"]``
without variants. Version and source commit are captured from the run context,
with null when unavailable. A job-only output has ``step: null``; declare outputs
on their producing steps when step-based lookup is needed. If the exact same path
is declared by a job and a step, the step declaration takes precedence.

Only existing files/directories from completed successful producers enter
``files``. Successful step outputs remain usable if a later step fails.
Missing paths, symlinks and failed/cancelled/skipped or detached GUI producers
are not upload candidates. Whole-job declarations require a complete successful
run with all steps passed; partial executions do not publish stale job outputs.
Cache-reused artifacts retain ``reused_from``. Paths or properties containing
masked secrets are excluded. These checks establish availability, not artifact
freshness, completeness or correctness.

The summary's ``outputs`` list includes resolved declarations that are unavailable
and their reasons. Steps excluded by selection or conditions do not resolve
their output declarations; ``upload_file`` identifies the manifest. A write failure is reported as
``upload_problem`` without changing the executed job's outcome. Log history
archives earlier manifests; workflow child snapshots copy the manifest so its
link cannot silently point to a later job run. Artifact contents are not copied
or restored, and a later build can replace files named in an old manifest.

A project uploader can read the configuration directly:

.. code-block:: python

   import json
   from pathlib import Path

   summary = json.loads(Path("_logs/debug/build/run.json").read_text())
   config = json.loads(Path(summary["upload_file"]).read_text())
   for artifact in config["files"]:
       # Upload artifact["path"] under the matrix destination, attaching
       # artifact["properties"] using the selected service's API.
       print(artifact["path"], artifact["properties"])

Use GitHub ``needs`` to choose producer job names when downloading. Combine that
name with version/commit/variant and, when needed, producer step and
``artifact_type``. There is no separate PTK input configuration.
