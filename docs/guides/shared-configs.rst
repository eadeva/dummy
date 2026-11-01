External configuration bases
============================

PTK ships no base configurations. A project selects one external Git repository
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

Ownership
---------

``destination`` is an unchanged external base. Do not edit it in the project.
PTK makes it read-only and records its repository, requested revision, resolved
commit, source path and SHA-256 contents in ``.ptk-configs.lock.json``. Keep bases
in a visibly named directory such as ``config/external``. Binary files remain
byte-for-byte copies too; PTK does not inject comments into external files.

``overlay`` belongs to the project. Only pre-commit, clang-format, clang-tidy and
clangd support YAML merging. An overlay requires a separate ``output``; PTK never
merges into the base. Generated outputs are read-only and carry provenance and
an instruction to edit the overlay. Maps merge recursively, lists/scalars replace,
and null removes keys. Pre-commit merges repositories by URL and hooks by ID;
clang-tidy combines check expressions and merges CheckOptions.

Ruff and arbitrary groups only copy files. The project authors its own
``ruff.toml``, using Ruff's native ``extend`` to reference the copied base.
PTK does not create or update this project file.

Commit bases, overlays, generated outputs, mapping configuration and the lock.
Git preserves executable bits but not read-only permissions: a fresh checkout may
be writable. Offline checks therefore verify contents and executable status,
not write permissions. Synchronization restores read-only permissions. These are
accidental-edit protection, not a security boundary; review and CX enforce ownership.

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
are rejected. Full 40/64-character hashes and version tags such as ``v2.4.0`` are
supported. Upgrading PTK does not change external bases.

Constraints
-----------

Git must be installed. HTTPS, SSH and local repositories use existing Git
credentials; do not embed HTTPS credentials or tokens in the URL. Git objects are
cached under ``.ptk/config-sources`` and exact cached commits work offline.
Preview may populate this cache. PTK reads regular Git blobs without checkout,
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
