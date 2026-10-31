GitHub Actions and callable workflow templates
==============================================

Generate a reviewable native GitHub workflow from PTK's configured graph::

   ptk maintainer gen-workflows verify
   ptk maintainer gen-workflows
   ptk maintainer gen-workflows verify --action-repository eadeva/dummy --action-ref COMMIT_SHA

The first command writes ``.github/workflows/ptk-verify.yml`` in the repository
owning ``verify``. With no names, all discovered workflows are generated. Existing
files are never overwritten, including on repeated generation: PTK prints a
warning. Generation is maintainer-only and does not execute jobs or contact
Artifactory. Review and commit the template; it is project-owned from then on.

Setup and dependencies
----------------------

Every generated workflow is callable through ``workflow_call``. Its first job,
``setup``, checks out the sources and calls::

   ptk maintainer matrix --workflow verify --format github

The setup export supplies ``matrix_<invocation>`` for each workflow invocation,
plus the ordinary ``matrix``, ``upload_base`` and ``has_jobs`` outputs. Each row
contains only execution information, parameters, its repository directory,
upload destination and producer selectors. Runtime output paths remain absent.
All routes share one setup timestamp, so consumers use exactly the destinations
selected for their producers, including job-specific suffixes.

Every execution job declares ``needs: [setup, ...configured_producers]``. Each
has a separate variant matrix. A consumer waits for all variants of its producer
jobs, then downloads only its selected producer variant. This deliberately avoids
using a matrix job's last-finishing output as an artifact selector. Invocation
IDs are translated to producing PTK job names. The reserved invocation name
``setup`` is rejected during generation.

Owner ``repo_variants`` mappings apply to VMR producers. Identical mapped calls
are deduplicated; conflicting parameters/dependencies for the same producer
identity fail setup and require selecting one owner variant. A configured call
that is ineligible for a selected variant also fails setup; PTK does not silently
remove dependency edges. Each execution calls one PTK job, never a PTK workflow.
``continue_on_error`` and ``max_workers`` map to job ``continue-on-error`` and
per-matrix ``max-parallel``. The latter is not a workflow-wide concurrency cap.

Project TODOs
-------------

* Supply a Linux Docker-capable ``runner`` and ``container-image``. The image
  must already provide the matching PTK release, Python 3.12+, Bash, curl and
  required project tools. Actions do not install PTK. Configure registry
  credentials, volumes and container permissions as needed.
* Create a caller workflow with the project's events (push, pull requests,
  schedules, etc.). The generated workflow does not choose events or runners.
* Pass ``PTK_ARTIFACT_USER`` and ``PTK_ARTIFACT_TOKEN`` as workflow secrets.
  Optional inputs are ``variants``, ``project-directory``, ``no-cache-ptk`` and
  ``additional-properties`` (a JSON object). Maintainer jobs still require the
  runner identity to be authorized by PTK.
* Review and pin action references to approved immutable commits. The default
  action repository/ref points at this implementation branch and is a template
  choice, not an automatic release-management policy.
* For a detected VMR, **every** ordinary checkout is replaced by a clearly
  labelled VMR-checkout TODO, including setup. The placeholder fails until
  replaced. Recreate the same configured repository layout and revisions in
  every job. The workflow owner directory is supplied as the default setup
  ``project-directory``; producer/execution directories come from the matrix.
* Configure Artifactory event routes and declare real job/step outputs.
  Empty output declarations publish an empty manifest, not inferred build
  folders. Project authors own output completeness and cache correctness.

The checked-in ``.github/workflows/ptk-verify.yml`` is generated from PTK's own
``verify`` workflow. It remains callable-only and requires the project inputs
above; generation does not dispatch a remote workflow. All five verify jobs
explicitly declare their final report directory. The test report directory
includes JUnit XML. Sphinx additionally declares its HTML directory, extension
packaging declares a stable ``project-toolkit.vsix`` under the step bin directory,
and package preparation declares its release directory (dist, offline docs,
checksums and manifest). These are configured outputs, not implicit defaults;
cache remains disabled unless the project explicitly enables it.

Action contracts
----------------

The three composite actions live under ``.github/actions``. Their runtime is
part of the installed PTK package; use matching Action/PTK versions.

``ptk-run-job``
~~~~~~~~~~~~~~~

Inputs: ``job`` (required), ``variant`` (one variant), ``working-directory``
(default ``.``), ``params`` (typed JSON object), ``no-cache`` and ``maintainer``
(boolean strings, default false). Job parameters use a temporary parameter file,
not shell interpolation. Configure secret job parameters through PTK environment
sources rather than literal workflow JSON.

Outputs: ``uploads-json`` is the exact completed execution's manifest path;
``output-paths`` is a JSON array of available repository-relative output paths.
The filename remains ``upload.json``; upload accepts any manifest filename.
A private result handoff connects the action to the completed job: it never
searches for a potentially stale "latest" log. The PTK exit status is preserved.
A successful job without a usable manifest fails the Action. The manifest and
available earlier-step outputs are exposed even when a later step fails.

``ptk-upload``
~~~~~~~~~~~~~~

Required inputs: ``base-url`` (the setup row's upload URL), ``uploads-json``,
``technical-user`` and ``token``. Optional inputs: ``producer`` (setup row JSON
for identity validation; otherwise read from the manifest),
``working-directory``, ``artifact-scope`` and ``additional_properties``.
``manifest-url`` is exposed only after all uploads succeed.

Files are uploaded directly using curl; each directory is ZIP-compressed,
including nested files and empty directories. ZIP entries retain ordinary Unix
permission bits. Output paths must be inside the producer repository and have a
portable ``relative_path`` in the manifest. An optional manifest ``upload_path``
changes its relative remote suffix; it does not change the restore location.
The completed-job manifest automatically supplies ``relative_path`` for internal
outputs. External outputs remain usable locally but fail Action validation.

Payloads live under the supplied base plus a deterministic producer namespace,
execution ID and output index, followed by their relative remote suffix.
This separates same-named files and different step provenance. Producer
repository/job/variant/version/commit and ``artifact-scope`` select a small
remote manifest. The default scope is GitHub repository/run ID; retries of the
same workflow can reuse successful producers from that run. An explicit scope
must match between uploads and downloads. Concurrent writers for the same
scope and producer identity are unsupported; choose separate scopes.

Producer properties (version, commit, variant aliases, job, step and optional
artifact type) are attached using Artifactory matrix parameters and retained in
the remote manifest. Additional properties may not replace identity fields.
The uploader verifies the manifest identity against setup. It publishes the
remote manifest last, after all payloads, including an empty manifest for jobs
with no outputs. Interrupted uploads may leave unreferenced payloads; retention
and cleanup belong to the project.

``ptk-download``
~~~~~~~~~~~~~~~~

Required inputs: ``needs`` (``toJSON(needs)``), ``producers`` (setup selectors),
``technical-user`` and ``token``. Optional inputs: ``working-directory`` (checkout
root), ``artifact-scope`` and fallback ``base-url``. A producer's setup upload URL
takes precedence over the fallback. Only selectors present in GitHub ``needs``
are accepted; setup is not an artifact producer. ``output-paths`` is a JSON array
of restored paths, relative to each producing repository.

The downloader retrieves the exact producer manifest, verifies identity/scope
and every SHA256 checksum, then restores files and unzips directories to the
producer's original repository-relative locations. In VMRs the matrix supplies
the producing repository directory below the checkout. Version, commit and
variant cannot accidentally select another run's outputs. No server-wide search
or "latest artifact" heuristic is used. All outputs from the requested producer
are downloaded; this version has no artifact-type filtering input.

Constraints
-----------

* HTTPS is required. curl credentials are passed through stdin, not process
  arguments; redirects and user curl configuration are disabled. Server errors
  report the operation and curl exit code without echoing credentials.
* Symlinks, special files, absolute/traversing paths and unsafe ZIP entries are
  rejected. Overlapping destination paths across declarations/producers fail
  before restoration. Select disjoint output paths; a directory and its child
  are not two independent outputs.
* Downloads replace each declared destination, removing stale directory
  contents. Do not declare source directories as outputs. Downloads and ZIPs are
  validated/staged before replacement, but replacement of multiple outputs is
  not transactional; an OS failure can leave a partially restored set.
* POSIX permission bits are preserved, not ownership, ACLs, extended attributes
  or timestamps as a reproducibility contract. ZIP symlinks are unsupported.
  Staging needs space for downloaded archives and expanded contents.
* Missing producer manifests/checksum failures fail the consumer. A tolerated
  failed producer may expose successful step outputs, but their completeness
  remains the project's responsibility. Upload is attempted after failed jobs,
  unless cancelled, when a manifest is available.
* The generated workflows target Linux job containers. Windows/macOS runners,
  container construction, remote publishing policy and Artifactory retention
  are not managed here. No live credentials or service access is required for
  generation or the automated transfer tests.

See :need:`REQ_Sw_CI_GENERATION`, :need:`REQ_Sw_GITHUB_ARTIFACTS` and
:need:`DD_GITHUB_ACTIONS` for the requirements and decisions.
