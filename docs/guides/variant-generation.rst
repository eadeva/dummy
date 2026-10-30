Reusable components and variant generation
==========================================

PTK owns the configuration contract: components declare their choices in YAML,
product variants select values, and PTK validates and resolves one snapshot before
execution. Projects own the implementation: build files decide which sources,
targets, compiler definitions and dependencies those values control. This division
is intentional so projects can use their own build conventions and scripts.

The accepted design records are :need:`DD_COMPONENT_VARIANTS`,
:need:`DD_STEP_GENERATORS` and :need:`DD_BUILD_ADAPTERS`. Requirements are
:need:`REQ_Sw_COMPONENT_SELECTIONS`, :need:`REQ_Sw_STEP_GENERATORS` and
:need:`REQ_Sw_GENERATORS`. The other team's proposal under
``reference/pmt_reuse_concept_variant_handling`` remains reference material;
PTK does not execute its CMake declaration/selection helper.

Declare choices; select a product
---------------------------------

Register components in ``config/ptk/project.ptk.yml``::

   name: controller
   components:
     motor: {path: src/motor}
     telemetry: {path: src/telemetry}

A component's ``src/motor/component.variants.ptk.yml`` describes its public
configuration. It does not select a product::

   description: Motor controller
   features:
     CONTROL_MODE:
       type: enum
       values: [OPEN_LOOP, CLOSED_LOOP]
       default: OPEN_LOOP
     DEBUG_LEVEL:
       type: int
       min: 0
       max: 3
       default: 0
     DIAGNOSTICS:
       type: bool
       default: false

``src/telemetry/component.variants.ptk.yml`` may independently declare
``DEBUG_LEVEL``. Its identity is ``telemetry.DEBUG_LEVEL``. Components use
lower_snake_case IDs; feature names use UPPER_SNAKE_CASE. Component IDs ``params``,
``vars``, ``env``, ``vh``, ``variant``, ``os`` and ``ci`` are reserved because they
name expression namespaces. Exports use uppercase identifiers. Ambiguous exports,
for example ``a.B_C`` and ``a_b.C``, are rejected during configuration validation.

Select values in ``config/ptk/variants/road.ptk.yml``::

   components: [motor, telemetry]
   features:
     motor.CONTROL_MODE: CLOSED_LOOP
     motor.DEBUG_LEVEL: 1
     motor.DIAGNOSTICS: true
     telemetry.DEBUG_LEVEL: 0

Set ``default: road`` in ``config/ptk/project.variants.ptk.yml``, or select the
product explicitly with ``ptk -V road build``. Temporary job overrides use
``ptk -V road build --feature motor.DEBUG_LEVEL=2``. Inspect the result with
``ptk variant show road`` and ``ptk variant explain road motor.DEBUG_LEVEL``.
Overrides do not edit YAML. Workflow jobs retain their explicit variant mappings.

The existing inheritance rules apply: parents resolve before children, later
assignments override earlier assignments, and an explicit ``components`` list
replaces the inherited list. Omitting the list throughout the inheritance chain
selects all registered components. Abstract variants provide shared selections
but cannot be built. Defaults come from the component; a missing boolean defaults
to false, integer to its minimum or zero, string to empty and enum to its first
option. Declare explicit defaults when that implicit policy is unsuitable.

Expressions use qualified names, including inside component-local constraints::

   constraints:
   - expr: motor.DEBUG_LEVEL == 0 or motor.DIAGNOSTICS
     message: Motor debugging requires diagnostics

Component constraints apply only when their component is selected. Feature
``depends_on``, ``requires`` and ``conflicts`` and project-wide constraints retain
their existing semantics. Required components must be selected explicitly; PTK
does not silently enable them. Invalid types, ranges, choices, dependencies and
inheritance cycles fail validation. An inactive boolean resolves to false;
an inactive non-boolean resolves to null. Explicit incompatible selections are
reported rather than quietly accepted.

.. list-table:: One identity across consumers
   :header-rows: 1
   :widths: 35 65

   * - Consumer
     - Example
   * - Product YAML, expressions, CLI override
     - ``motor.DEBUG_LEVEL``
   * - PTK substitution
     - ``${vh.features.motor.DEBUG_LEVEL}``
   * - Environment and generated build variable
     - ``VARIANT_MOTOR_DEBUG_LEVEL``
   * - Component selection in expressions
     - ``COMPONENT_MOTOR`` or ``vh.components.motor`` in job conditions
   * - Component selection in exports/environment
     - ``VARIANT_COMPONENT_MOTOR``
   * - Product name
     - ``VARIANT_NAME``

Environment values are strings: booleans become 0/1 and null becomes empty.
``VARIANT_COMPONENTS`` is an environment-only space-separated list. Exports carry
component flags, feature values and the product name. Arbitrary variant ``data``
is available to substitutions and custom generators, but is not copied into the
built-in formats. Enumeration values remain strings; PTK does not assign ordinal
C preprocessor numbers based on the order of an enum's choices.

Generate for a step
-------------------

Declare ``generators`` directly on the consuming step in ``jobs/build.ptk.yml``::

   steps:
     configure:
       generators: [cmake, header]
       run:
       - cmake
       - -S
       - .
       - -B
       - ${run.build_dir}/cmake
       - -DPTK_VARIANT_FILE=${run.build_dir}/variant.cmake
     compile:
       needs: [configure]
       run: [cmake, --build, "${steps.configure.build_dir}/cmake"]

The same field works on Python and ``uses`` steps::

   steps:
     prepare:
       generators: [make, cmake, bazel, gn]
     script:
       generators: [cmake]
       run: tools/configure.py
       python: {interpreter: cli}
       env:
         PTK_VARIANT_FILE: ${run.build_dir}/variant.cmake

A generation-only step is valid. The list is ordered, contains unique literal
names, and may include generators from enabled plugins. ``run`` and ``uses``
remain mutually exclusive. No generators run unless listed.

The resolved variant, including job feature overrides, is captured during
preparation. All generators in that run receive that same resolved configuration,
with a separate copy per plugin invocation. Changes to configuration files during
the run do not alter that snapshot.

Generation happens before each execution attempt, inside the step's timeout and
cancellation scope. Command retries regenerate files. A generator exception fails
the step before its command/script/plugin runs and is not itself retried. Normal
``continue_on_error`` and dependency handling still apply. Cancellation is checked
between generator calls and file writes; trusted synchronous Python plugins must
return before PTK can observe cancellation or a timeout.

Dry runs and graph previews list generators without invoking them. Skipped,
blocked and unselected steps do not generate. Preparation rejects unknown enabled
step generators and generation without a selected valid variant before any step
starts. Configuration discovery and the editor do not execute generators.

Outputs always go to the owning step's ``${run.build_dir}``, normally
``_builds/<variant>/<job>/<step>/``. Generation does not change the command's cwd;
the repository root remains the default. Python scripts should receive the path
explicitly through arguments or ``env``. Another step can use
``${steps.prepare.build_dir}`` and must declare ``needs: [prepare]``. A dependency
orders execution; it neither transfers nor validates the files.

Files are UTF-8 with LF endings. Returned paths must stay inside the step folder;
absolute paths, traversal, symlinks, case-insensitive filename collisions and
file/directory conflicts fail before writing. PTK replaces each file atomically,
but does not provide a multi-file transaction or remove stale files from an older
generator selection. Projects own build cleanup. Generated files must not be
edited manually.

Build-tool integrations
-----------------------

.. list-table:: Bundled formats
   :header-rows: 1
   :widths: 15 25 60

   * - Generator
     - Output
     - Consumer contract
   * - ``make``
     - ``variant.mk``
     - GNU Make assignments; booleans 0/1, inactive null empty.
   * - ``cmake``
     - ``variant.cmake``
     - Ordinary CMake variables; booleans 0/1, inactive null empty; no forced cache entries.
   * - ``bazel``
     - ``variant.bazel.json``
     - Versioned typed JSON for the project-owned repository helper below.
   * - ``gn``
     - ``variant.gni``
     - GN assignments; native booleans/integers/strings; inactive null omitted.
   * - ``header``
     - ``variant.h``
     - C macros; booleans 0/1, strings quoted, inactive null omitted.
   * - ``yocto``
     - ``variant.inc``
     - BitBake assignments; booleans 0/1, inactive null empty.
   * - ``robot``
     - ``variant.robot``
     - Robot variable table with escaped text values.
   * - ``sphinx``
     - ``variant.rst``
     - RST containing the resolved values as JSON.

Make rejects newlines, backslashes and surrounding whitespace; Yocto rejects
newlines and variable expansions. GN rejects newlines/NUL in strings and integers
outside the signed 64-bit range. Unsupported values fail explicitly. Other tools
can impose their own target/API restrictions after importing a valid file.

CMake
~~~~~

The project consumes the generated file directly::

   # CMakeLists.txt, before configuring component targets
   if(NOT DEFINED PTK_VARIANT_FILE)
     message(FATAL_ERROR "PTK_VARIANT_FILE is required")
   endif()
   include("${PTK_VARIANT_FILE}")
   add_subdirectory(src/motor)

The component can use ``VARIANT_MOTOR_CONTROL_MODE`` in an ``if(... STREQUAL ...)``
and configure its own targets. If a source library needs numerical enum macros,
the project maps names to explicit stable numeric values or supplies its own
header generator. PTK does not turn enum positions into an ABI.

The proposed CMake helper is not needed to declare features, apply defaults or
choose the product: PTK already does those operations. A project may keep a small
adapter that includes the generated file and maps values onto target properties.
It must not introduce another variant-selection authority or global cache writes
shared by concurrent configurations. CMake's ordinary variable scope still applies;
include at the common parent scope or inside each consumer as appropriate.

GNU Make
~~~~~~~~

Pass the generated path explicitly::

   generators: [make]
   run: [make, "PTK_VARIANT_FILE=${run.build_dir}/variant.mk", "BUILD_DIR=${run.build_dir}/make"]

In the project Makefile::

   include $(PTK_VARIANT_FILE)
   ifeq ($(VARIANT_MOTOR_CONTROL_MODE),CLOSED_LOOP)
   # Select project-owned sources/flags here.
   endif

The project controls quoting, target dependency declarations and out-of-tree object
paths. Make's include filename handling needs additional care if the path contains
spaces. A command-line or override assignment can change Make variables; avoiding
such conflicting selections is a project integration responsibility.

GN (Generate Ninja)
~~~~~~~~~~~~~~~~~~~

GN reads a ``.gni`` file during ``gn gen``; GN then creates Ninja build files.
There is no PTK plain-Ninja generator. For a step folder under the GN source root,
pass a source-absolute GN path as a declared build argument::

   generators: [gn]
   run:
   - gn
   - gen
   - ${run.build_dir}/gn
   - '--args=ptk_variant_file="//_builds/${vh.variant}/build/configure/variant.gni"'

The literal relative portion in that example assumes the default layout, job
``build`` and step ``configure``. Adapt it if the GN source root or PTK layout
changes; GN ``//`` means the GN source root, not the filesystem root. A project
wrapper can compute this path from ``${run.build_dir}``.

In the project's common GN configuration::

   declare_args() {
     ptk_variant_file = ""
   }
   assert(ptk_variant_file != "", "Select the generated PTK configuration")
   import(ptk_variant_file)
   # Use VARIANT_MOTOR_CONTROL_MODE and VARIANT_COMPONENT_MOTOR in targets.

Projects must arrange import scope and keep generated inputs visible to the GN
source tree. Do not copy a shared mutable configuration over another variant's file.

Bazel
~~~~~

Bazel cannot load an arbitrary absolute ``.bzl`` file from a step folder as if it
were a workspace label. The PTK generator therefore emits data, and the project
adapts it through a local external repository. The JSON contract is
``{"schema_version": 1, "values": {"VARIANT_NAME": "road", ...}}`` with boolean,
integer, string or null values. Enum choices are strings.

Download :download:`ptk_variants.bzl <../resources/bazel/ptk_variants.bzl>` and copy
it into the **consuming project**, for example ``build_support/ptk_variants.bzl``.
Add ``build_support/BUILD.bazel`` so the file has a package label. This helper is
a documentation resource, not a PTK runtime module or installed built-in.
The project owns and can adapt the copy.

With Bzlmod, in ``MODULE.bazel``::

   ptk_variants = use_repo_rule("//build_support:ptk_variants.bzl", "ptk_variants")
   ptk_variants(name = "ptk_variant")

The PTK step can then run::

   generators: [bazel]
   run:
   - bazel
   - --output_base=${run.build_dir}/bazel-output
   - build
   - --repo_env=PTK_VARIANT_FILE=${run.build_dir}/variant.bazel.json
   - --symlink_prefix=/
   - //app:firmware

``PTK_VARIANT_FILE`` must be an absolute path on the machine running Bazel's
repository evaluation. It is passed with ``--repo_env`` rather than a global
shell mutation. ``--symlink_prefix=/`` disables convenience symlinks so parallel
builds do not rewrite the same workspace links.

The helper exposes a constant dictionary for loading-time decisions::

   load("@ptk_variant//:variant.bzl", "VARIANT")
   # VARIANT["VARIANT_MOTOR_CONTROL_MODE"] == "CLOSED_LOOP"

It also creates public typed build settings for ``config_setting``/``select()``::

   config_setting(
       name = "closed_loop",
       flag_values = {
           "@ptk_variant//:VARIANT_MOTOR_CONTROL_MODE": "CLOSED_LOOP",
       },
   )
   # In a project rule's configurable attribute:
   # deps = select({":closed_loop": [":closed_loop_impl"],
   #                "//conditions:default": [":open_loop_impl"]})

Settings are not command-line flags: PTK remains the selection authority. Null
inactive non-boolean features remain ``None`` in the dictionary and have no typed
setting. Gate those targets on component selection rather than referring to an
absent setting. The helper tracks the JSON file and repository environment, so
changing content at the same path or selecting a new path causes reevaluation.
Schema versions and unsupported value types are checked explicitly.

One external repository represents one resolved PTK configuration per Bazel
invocation. Building several PTK products means separate Bazel invocations and
output bases; this is not a Bazel transition framework. Remote action execution
can consume Bazel's resulting configuration, but the helper still needs the local
snapshot at repository evaluation time. The helper targets Bzlmod; it does not
provide a legacy WORKSPACE fallback.

Parallel execution and responsibilities
---------------------------------------

Different variants, jobs and steps have different default build folders. Repeating
the same variant/job/step uses the same path: there is no per-run build-folder
isolation. Avoid overlapping runs of that same identity or provide separately
isolated workspaces/layout roots. Steps without dependencies may execute in
parallel. CLI multi-variant batching currently executes prepared variants in
sequence; extension selections launch separate tasks. Concurrent CLI variant
scheduling remains open under :need:`REQ_Sw_MULTI_VARIANT`.

Projects must choose separate CMake/GN build trees, Make object folders and Bazel
output bases for concurrent configurations. Bazel caches, module lockfiles,
convenience symlinks, downloads and any other shared mutable state must follow
the project's concurrency policy. A dependency edge does not lock external state.

PTK does not monitor what project scripts read or write and does not sandbox
steps. The generated configuration is an input contract; PTK cannot prove the
build consumed it correctly or that outputs are valid. Projects own artifact
validation, input/output declarations, compiler mapping, reproducibility,
retry-safe side effects, cancellation cleanup and any necessary rollback.
A successful step means its execution succeeded. This boundary deliberately
preserves project flexibility; see :need:`DD_EXECUTION_BOUNDARIES`.

Compatibility and verification
------------------------------

This replaces unqualified product feature keys, ``${vh.features.FEATURE}``,
custom export prefixes, ``VH_*``/``BO_*`` exports and ``uses: variant.generate``.
Update configurations explicitly; PTK does not silently translate old forms.
The extension consumes PTK's canonical schema and keeps invalid documents editable;
validation errors must not prevent opening the editor or correcting YAML.

``tests/test_step_generators.py`` covers execution ordering, prepared snapshots,
retries, skipped/blocked work, cancellation, path validation and separate output
folders. ``tests/unit/test_variants.py`` covers qualified identities and collisions.
``tests/test_generators.py`` exercises native CMake consumption.
``tests/test_native_variant_builds.py`` exercises GNU Make, GN imports and Bazel
settings, constants, changed-file reevaluation and schema rejection. GN/Bazel
checks are opt-in via ``PTK_TEST_GN`` and ``PTK_TEST_BAZEL`` executable paths; they
are skipped when those variables are absent. The initial native verification used
CMake 3.30.9, GNU Make 4.3, GN 2614 and Bazel 9.1.0 on Linux; this is evidence for
those versions, not a claim that every platform/version was tested.

Primary build-tool references:
`CMake include <https://cmake.org/cmake/help/latest/command/include.html>`_,
`GNU Make include <https://www.gnu.org/software/make/manual/html_node/Include.html>`_,
`GN reference <https://gn.googlesource.com/gn/+/main/docs/reference.md>`_,
`Bazel build settings <https://bazel.build/extending/config>`_ and
`Bazel repository rules <https://bazel.build/extending/repo>`_.
