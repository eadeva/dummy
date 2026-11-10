External configuration bases
============================

PTk ships no base configurations. A project selects one external Git repository
and an immutable commit hash or version tag, then maps individual source files
into its own repository. Only maintainers synchronize these files::

   # config/ptk/configs.ptk.yml
   source:
     repository: https://github.com/example/development-configs.git
     revision: v2.4.0
   clang-format:
     files:
       - source: cpp/clang-format.yaml
         destination: config/external/clang-format.yaml
         overlay: config/overlays/clang-format.yaml
         output: .clang-format
   pre-commit:
     hook_config: .pre-commit-config.yaml
     files:
       - source: python/pre-commit.yaml
         destination: config/external/pre-commit.yaml
         overlay: config/overlays/pre-commit.yaml
         output: .pre-commit-config.yaml
   ruff:
     files:
       - source: python/ruff.toml
         destination: config/external/ruff-base.toml

Replace the example repository and revision with your organization's source.
Each group can declare multiple files; custom lowercase groups are also supported.
Paths are literal repository-relative paths, not globs. Source paths are relative
to the external repository. Destinations, overlays and outputs are relative to the
consuming repository. Overlapping managed paths and overlays are rejected.

A ``source`` and ``destination`` that both end in ``/`` map a whole folder
recursively: every regular file below the source folder at the pinned revision
is copied to the same relative path below the destination, and recorded per file
in the lock (with its ``mapping``). Folder mappings cannot have overlays. Files
removed upstream stay in the project until you delete them::

   helix:
     files:
       - source: tools/perforce_qac/2025.4/config/
         destination: build_environment/ptk/helix/config/

Ownership
---------

``destination`` is an unchanged external base. Do not edit it in the project.
PTk leaves it writable and records its repository, requested revision, resolved
commit, source path and SHA-256 contents in ``.ptk-configs.lock.json`` inside
``repository.config_path``. For ``config_path: config/ptk``, the lock is
``config/ptk/.ptk-configs.lock.json``, beside ``configs.ptk.yml``. All sync, check
and deviation-report commands use this location; no root-level fallback is read.
Keep bases
in a visibly named directory such as ``config/external``. Binary files remain
byte-for-byte copies too; PTk does not inject comments into external files.

``overlay`` belongs to the project. Only pre-commit, clang-format, clang-tidy and
clangd support YAML merging. An overlay requires a separate ``output``; PTk never
merges into the base. Generated outputs remain writable and carry provenance and
an instruction to edit the overlay. Maps merge recursively, lists/scalars replace,
and null removes keys. Pre-commit merges repositories by URL and hooks by ID;
clang-tidy combines check expressions and merges CheckOptions.

Ruff and arbitrary groups only copy files. The project authors its own
``ruff.toml``, using Ruff's native ``extend`` to reference the copied base.
PTk does not create or update this project file.

Commit bases, overlays, generated outputs, mapping configuration and the lock.
PTk does not apply filesystem write protection. Ownership is documented and
checked using content hashes; a locally modified file still blocks synchronization.
Validation ignores write permissions and checks executable status where supported.
Synchronization writes normal writable files, including files made read-only by
an earlier synchronization.

Deviation report
----------------

Run the maintainer-only command::

   ptk maintainer configs-report
   ptk maintainer configs-report --output _reports/policy-review.json

The default output is ``_reports/config-deviations.json``, relative to the repository.
The command uses local files and the committed lock without fetching. It writes
JSON with these sections:

* ``deviations``: configured generated outputs that differ from their verified
  bases, with group, base, overlay, output, ``output_matches_sync`` and unified diff.
* ``modified_base_files``: only the filenames of external bases whose bytes differ
  from their recorded hashes. No base-content diffs are included in this section.
* ``unavailable``: missing bases/outputs, unsynchronized mappings, invalid YAML
  or comparisons omitted because their base was modified.

The report includes source/revision and the pinned commit. Differences use
normalized YAML, ignoring comments, key ordering and formatting, including PTk's
provenance comments. Lists retain their order. Comparisons use the current output
on disk, not a newly merged overlay: synchronize after editing overlays to review
new effective settings. ``output_matches_sync: false`` identifies output content
that changed since synchronization, independently of whether that change came
from a person or another tool.

Example (diff shortened)::

   {
     "deviations": [
       {
         "group": "clang-format",
         "base": "config/external/clang-format.yaml",
         "overlay": "config/overlays/clang-format.yaml",
         "output": ".clang-format",
         "output_matches_sync": true,
         "diff": "... -ColumnLimit: 100 ... +ColumnLimit: 120 ..."
       }
     ],
     "modified_base_files": ["config/external/ruff-base.toml"],
     "unavailable": [
       {"path": "config/external/ruff-base.toml", "reason": "base modified; comparison omitted"}
     ]
   }

Only enabled, explicitly mapped configurations are inspected. A missing file is
reported as unavailable, not as modified. Unsynchronized source changes require
synchronization first. PTk never uses a modified base as the reference for a diff.
Ruff's project-owned ``ruff.toml`` and arbitrary native inheritance mechanisms are
outside this report: PTk checks their copied bases but does not infer their
project-specific effective configuration.

An existing PTk deviation report can be replaced. Authored files and mapped bases,
overlays or outputs cannot be report destinations. Successful report generation
returns success even when findings exist; use ``ptk validate --generated`` for a
freshness gate. Reporting neither repairs nor synchronizes configuration files.

Updating and checking
---------------------

* ``ptk maintainer sync configs --diff`` fetches as needed and previews changes.
* ``ptk maintainer sync configs`` synchronizes all enabled groups.
* ``ptk maintainer sync configs clang-format`` selects a group.
* ``ptk maintainer sync configs --check`` checks locally without fetching.
* ``ptk validate --generated`` provides the same offline check to ordinary users/CX.

Synchronization and its preview require maintainer access. There is no
``configs.sync`` job step. Jobs, doctor and validation never fetch configurations.
An existing differing file is replaced only when its contents still match the
previously recorded managed version. Edited bases/generated outputs and differing
unowned files block synchronization before destination writes; review and resolve
the conflict explicitly. There is no force overwrite flag.

The first synchronization resolves a version tag to a commit; subsequent syncs
keep that commit even if the tag moves. Change the revision explicitly to upgrade.
A source/revision change requires a full sync, not a selected group. Branch names
are rejected. Full 40/64-character hashes and version tags with two to four
numeric parts, an optional ``v`` prefix and an optional ``-``/``+`` suffix (such as
``v2.4.0`` or ``v26.45.00.01``) are supported. Upgrading PTk does not change external bases.

Constraints
-----------

Git must be installed. HTTPS, SSH and local repositories use existing Git
credentials; do not embed HTTPS credentials or tokens in the URL. Git objects are
cached under ``.ptk/config-sources`` and exact cached commits work offline.
Preview may populate this cache. PTk reads regular Git blobs without checkout,
filters, hooks or submodules. Symlinks, directory mappings and path traversal are
rejected. Each file is limited to 100 MiB; each Git operation has a 120-second timeout.

Removing/disabling a mapping drops its ownership record on full sync but leaves
its existing files untouched. Review and remove obsolete files yourself. Each
replacement is atomic, with the lock written last; multiple files are not one
filesystem transaction. An I/O failure can leave a partially synchronized set;
rerun synchronization after resolving it. Offline checks verify the committed
lock and local contents, not remote tag state or signatures. Review lock changes
alongside files; the lock is provenance, not an independent trust authority.

For project-owned pre-commit configuration, ``pre-commit: {enabled: true}`` with
no files is sufficient to enable hook installation without an external source.
``hook_config`` optionally selects that configuration's location.
