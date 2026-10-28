Version discovery and generated build files
===========================================

PTK discovers versions; it never bumps versions, commits changes or creates tags.
Put maintained rules in ``versioning.ptk.yml`` in ``repository.config_path``.
The file contains the versioning body without a ``versioning`` wrapper and owns all version rules.
A project without versioning configuration runs as before.

Every configured job run resolves versions once after variant selection and
before its steps. Execution atomically writes a unique snapshot to::

   .ptk/versions/<variant>/<job>/<run-id>/.gen.version.ptk.yml

``PTK_VERSION_FILE`` points to that snapshot. Steps and generators share the same
resolved values even if a step changes Git state or a source manifest. Subsequent
runs discover again. Snapshots are retained until the user removes them; they are
not included in log-history rotation. Add ``.gen.version.ptk.yml`` to ``.gitignore``
(the initializer does this). Generated snapshots are excluded from configuration discovery
and refused as explicit configuration inputs. They never feed back into discovery.
Dry runs discover versions but do not write snapshots or execute job steps.
Custom discovery commands still execute in a dry run: they must be read-only.

Sources
-------

A minimal configuration::

   # config/ptk/versioning.ptk.yml
   project:
     source: literal
     version: 1.2.3
   components:
     core: {}
     sdk:
       source: file
       path: components/sdk/pyproject.toml
       format: toml
       key: project.version

Components declared in the variant model also inherit automatically unless
explicitly configured here. Components can have independent versions even when
not modeled as variant components. All configured components are resolved,
including components disabled in the selected variant. This gives the snapshot
a stable catalog; use generator ``components`` to select a subset.

Supported sources:

* ``literal``: required string ``version``.
* ``git``: reachable tags filtered by ``match`` (default ``v*``),
  ``strip_prefix``, ``first_parent`` (default true), ``dirty``
  (``suffix``, ``ignore`` or ``error``), and ``allow_shallow`` (default false).
* ``file``: repository-relative ``path``; ``format`` is ``text`` (default),
  ``json``, ``toml`` or ``yaml``. Structured formats require a dotted ``key``
  whose value is a string. Text can use ``regex`` (named ``version`` group,
  otherwise the first capture, otherwise the entire match).
* ``env``: required ``variable`` read from PTK's caller environment.
* ``command``: an argv list in ``command``, run in the repository root with
  caller environment and ``timeout`` seconds (default 30). No implicit shell.
* ``inherit``: component default, using the resolved project version.

Non-Git sources support ``strip_prefix`` and ``regex``. ``fallback`` can contain
another complete source definition, used only on a discovery failure; its use
is recorded in the snapshot. Without a fallback, failures stop the run before
steps start. Do not use secret-bearing outputs as versions: versions are public
build metadata and are written to files and environment variables.

Git discovery uses ``git describe --tags --long --match PATTERN`` with optional
``--first-parent``. It selects reachable history, not the highest numeric tag
anywhere in the repository. Full history/tags are expected; shallow repositories
fail unless explicitly allowed. Dirty state includes tracked modifications,
not untracked files. At an exact clean ``v1.2.3`` tag, stripping ``v`` yields
``1.2.3``. Two commits later it yields ``1.2.3+2.gHASH``; dirty suffix mode adds
``.dirty`` (or ``+dirty`` at the tag). The raw describe output, full commit,
matched tag, distance, dirty flag and shallow flag remain in the snapshot.

Existing variant release lines
------------------------------

Variant overrides replace the selected source definition; specify all needed
source settings. Variant names must exist in the project's variant model::

   # config/ptk/versioning.ptk.yml
   project:
     source: git
     match: v*
     strip_prefix: v
   variants:
     a:
       project:
         source: git
         match: v1.*
         strip_prefix: v
     b:
       project:
         source: git
         match: v2.*
         strip_prefix: v
   components:
     core: {}

An inheriting component follows the selected project's release line. An explicit
component source remains independent. ``variants.NAME.components`` can override
individual component sources as well.

Names and VMR dependencies
--------------------------

The repository alias, not the project display name, qualifies every variable::

   PTK_VERSION_ENGINE=1.2.3
   PTK_VERSION_ENGINE_MAJOR=1
   PTK_VERSION_ENGINE_MINOR=2
   PTK_VERSION_ENGINE_PATCH=3
   PTK_VERSION_ENGINE_PRERELEASE=
   PTK_VERSION_ENGINE_BUILD_METADATA=
   PTK_VERSION_ENGINE_RAW=v1.2.3-0-gHASH
   PTK_VERSION_ENGINE_GIT_COMMIT=...
   PTK_VERSION_ENGINE_GIT_DISTANCE=0
   PTK_VERSION_ENGINE_GIT_DIRTY=false
   PTK_VERSION_ENGINE_GIT_TAG=v1.2.3
   PTK_VERSION_ENGINE_COMPONENT_SDK=3.0.0

The same suffixes apply to components. SemVer numeric fields are only exposed
when the resolved value has SemVer structure; custom strings and calendar
versions are preserved without invented numeric fields. Names normalize to
uppercase with hyphens replaced by underscores. Collisions, including between
names and field suffixes, fail explicitly. ``PTK_VERSION_*`` is reserved;
job/step overrides must not redefine discovered values. Stale caller version
variables are removed before the current snapshot's variables are injected.

Only the current repository is resolved by default. Explicit VMR dependencies
can be declared globally or on individual jobs::

   # config/ptk/versioning.ptk.yml
   project:
     source: literal
     version: 1.2.3
   dependencies:
     frontend:
       variant: release

   # config/ptk/jobs/package.ptk.yml
   version_dependencies:
     engine:
       variant: debug
   steps:
   - show:
       uses: echo
       with:
         message: Frontend ${version.projects.frontend.value}

Dependency variants are mandatory when the dependency has variants; no implicit
mapping from the caller's variant occurs. Dependencies resolve recursively;
cycles and conflicting variant selections fail. Loading another repository's
versions does not import its tools or job environment. Dependencies must be
members of the same detected VMR and have versioning configured.

Structured substitutions are available in job environments, parameters and
steps, for example ``${version.projects.engine.value}``,
``${version.projects.engine.major}``, and
``${version.projects.engine.components.sdk.value}``.
The built-in/plugin context exposes the same mapping as ``ctx.versions``.
Treat it as read-only.

``${version.current.*}`` is a template shortcut for the current repository's
entry. ``sort_key`` adds four-digit numeric components for destination folder
ordering; ``1.2.3`` becomes ``0001_0002_0003``. See :doc:`artifacts` for its
numeric limits and prerelease ordering boundary. The underlying version value
and generated package version are unchanged.

Build generators
----------------

Use the built-in ``version.generate`` to render the prepared snapshot::

   - header:
       uses: version.generate
       with:
         format: c_header
         project: engine
         components: [core, sdk]
         output: "${run.bin_dir}/generated/version.h"
   - cmake:
       uses: version.generate
       with:
         format: cmake
         output: "${run.bin_dir}/generated/version.cmake"

``project`` selects one resolved repository; omit it to export all. ``components``
selects components within an explicitly selected project; omit it to export all.
The project version is always included. Supported formats and default filenames
are ``c_header``/``header`` (``version.h``), ``cmake`` (``version.cmake``),
``msbuild`` (``version.props``), ``python`` (``version.py``), and ``json``
(``version.json``). Without ``output``, files go in that step's build directory.
Relative output paths resolve from the repository root. Values are escaped for
each target format. Raw/Git provenance is excluded unless ``provenance: true``;
version strings still include any configured Git distance/dirty suffix.

Writes are atomic and unchanged contents preserve the existing file's timestamp.
CMake consumers can ``include`` the generated file, MSBuild can ``Import`` the
props file, and C/C++ can include the header. These generators do not mutate
existing build scripts or package manifests. Choose distinct output paths for
concurrent jobs/variants; their automatic snapshots are already unique.

CLI
---

::

   ptk -V debug version show
   ptk -V debug version check
   ptk -V debug version generate
   ptk -V debug version show --job package
   ptk -V debug engine version show       # in VMR mode

``show`` includes inheritance and provenance. ``check`` performs discovery without
writing. ``generate`` writes a snapshot to a unique directory or ``--output``;
the output filename must be ``.gen.version.ptk.yml``. There are no version mutation
or release commands. Normal job execution generates its snapshot automatically.
