Architecture decisions
======================

These records capture the established decisions from the project discussion and
the resulting implementation. ``ddec`` (Design Decision), with ``DD_`` IDs, follows
the supplied meta-model. It is registered explicitly; no meta-model YAML is loaded.
Requirements remain in :doc:`/requirements/index`. A decision's acceptance does
not imply that every related future capability has been implemented.

.. needtable:: Established decisions
   :filter: type == "ddec"
   :columns: id;title;status
   :style: TABLE

.. ddec:: A shared CLI with project-owned functionality
   :id: DD_PURPOSE
   :status: accepted

   **Context:** Projects need a familiar interface without centralizing every build tool.

   **Decision:** PTK standardizes variants, parameters, setup, credentials, execution, logging and reporting. Projects own the commands and domain-specific behavior. Workflow/job/step names follow GitHub terminology; PTK supports CX work beyond CI.

   **Alternatives considered:** A monolithic CLI containing each project tool would couple their release cycles.

   **Consequences:** PTK provides stable orchestration and contracts; projects remain responsible for their scripts and external tools.

   **Related requirement:** :need:`REQ_Stkh_INTEGRATION`.

.. ddec:: Separate domain rules from integrations
   :id: DD_CLEAN_ARCHITECTURE
   :status: accepted

   **Context:** Configuration and scheduling rules must remain testable across hosts.

   **Decision:** Keep pure domain models and rules inward, application use cases behind ports, and filesystem/process/editor adapters at the boundary.

   **Alternatives considered:** Embedding host operations in models would make validation depend on runtime side effects.

   **Consequences:** CLI and editor clients share the application contracts; published configuration documentation does not become a Python API catalogue.

   **Related requirement:** :need:`REQ_Sw_SCHEMA_AUTHORITY`.

.. ddec:: Fixed document ownership and component-local variants
   :id: DD_FIXED_DOCUMENTS
   :status: accepted

   **Context:** Recursive fragments and merge precedence made decentralized authoring hard to predict.

   **Decision:** Retain .main.ptk.yml as the marker; load known section/entity documents under repository.config_path. Register component paths and keep component.variants.ptk.yml beside component sources. Reject duplicate ownership.

   **Alternatives considered:** Arbitrary recursive discovery and include chains were rejected.

   **Consequences:** File placement is constrained but discoverable; an edit has a definite owning document.

   **Related requirement:** :need:`REQ_Sw_FIXED_LAYOUT`.

.. ddec:: PTK is the loading and metadata authority
   :id: DD_ONE_LOADER
   :status: accepted

   **Context:** An independent editor loader can disagree with the executable version.

   **Decision:** PTK supplies loaded values, schemas, provenance, file ownership, option choices, variable catalogues and dependency graphs. The extension consumes that versioned interface.

   **Alternatives considered:** Duplicating parsing and graph inference in the extension was rejected.

   **Consequences:** Generic model additions can appear after refresh. Breaking interface changes require coordinated CLI and extension updates.

   **Related requirement:** :need:`REQ_Sw_SCHEMA_AUTHORITY`.

.. ddec:: One current configuration and editor protocol
   :id: DD_NO_LEGACY
   :status: accepted

   **Context:** PTK has no deployed installed base requiring compatibility with experimental formats.

   **Decision:** Reject superseded syntax and unsupported editor protocol versions. Do not ship conversion parsers, migration layers or legacy rendering paths.

   **Alternatives considered:** Temporary dual formats were rejected because they multiply ambiguity and tests.

   **Consequences:** Repository configuration, examples, docs, tests and extension must move together when a contract changes.

   **Related requirement:** :need:`REQ_Sw_NO_LEGACY`.

.. ddec:: Separate project work from self-service and maintenance
   :id: DD_CLI_GROUPS
   :status: accepted

   **Context:** A flat command list hides everyday work among administrative operations.

   **Decision:** Expose jobs and workflows directly, place user setup under self-service and authoring operations under maintainer. Keep init separate. Validation remains available without a valid project and offers initialization guidance.

   **Alternatives considered:** Keeping every setup and authoring command at the root was rejected.

   **Consequences:** Explicit run/workflow run routes remain useful for scripts and name collisions; role checks still happen in PTK.

   **Related requirement:** :need:`REQ_Sw_NAMESPACES`.

.. ddec:: Workflows contain job dependency graphs
   :id: DD_WORKFLOW_NEEDS
   :status: accepted

   **Context:** Local cross-repository execution needs joins and partial ordering.

   **Decision:** Use a jobs mapping keyed by invocation ID, with job targets and needs edges. VMR targets use REPO:JOB. Validate graph and known output/environment conflicts before execution; bound ready jobs with max_workers.

   Each repository/job pair may appear once per workflow; see the identity and
   configuration-time validation clarification in :need:`DD_GRAPH_EDITING`.

   **Alternatives considered:** Sequential/parallel groups and positional step lists were rejected.

   **Consequences:** Failures block dependent chains, independent branches continue, and tolerated failures remain visible. Workflows run locally; CX orchestration remains external.

   **Related requirement:** :need:`REQ_Sw_WORKFLOWS`.

.. ddec:: Jobs use the same dependency semantics for steps
   :id: DD_STEP_NEEDS
   :status: accepted

   **Context:** Steps can operate in separate output folders, and nesting limits useful concurrency.

   **Decision:** Use a flat steps mapping with explicit needs and one run or uses per node. Apply conditions, retries, timeouts and continue_on_error to individual steps. Reuse the bounded dependency scheduler.

   **Alternatives considered:** Keeping ordered lists, nested groups or a second background scheduling mechanism was rejected.

   **Consequences:** Authors must declare ordering. A skipped prerequisite blocks dependents, and limits on concurrent jobs and steps compose. Edges do not declare or validate artifact inputs/outputs; :need:`DD_EXECUTION_BOUNDARIES` defines that responsibility boundary.

   **Related requirement:** :need:`REQ_Sw_CONTROL`.

.. ddec:: Keep the repository root as the default working directory
   :id: DD_ROOT_CWD
   :status: accepted

   **Context:** Many project commands expect paths relative to the repository.

   **Decision:** Retain repository-root cwd. Provide per-step build, log and report paths and explicit steps.ID path references; describe them as storage conventions, not an enforced sandbox.

   **Alternatives considered:** Changing default cwd to the step build folder was explicitly rejected.

   **Consequences:** Commands can write elsewhere. Authors must coordinate shared writes and external resources; PTK catches known uv environment conflicts but cannot infer arbitrary script behavior. Composed environments and cleanup path guards do not sandbox executed commands; see :need:`DD_EXECUTION_BOUNDARIES`.

   **Related requirement:** :need:`REQ_Sw_ENVIRONMENT`.

.. ddec:: Project implementation owns script behavior to preserve flexibility
   :id: DD_EXECUTION_BOUNDARIES
   :status: accepted

   **Context:** Projects use different languages, build systems, artifact layouts,
   caches, hardware and remote services. They need to integrate existing scripts
   and choose the execution guarantees appropriate to their work. PTK cannot
   infer the meaning or correctness of arbitrary project script operations from
   a command, dependency edge or output path.

   **Decision:** Deliberately assign project-specific script behavior and its
   correctness to the **project implementation**. PTK validates
   declared dependency graphs, schedules their nodes, composes environments,
   provides storage conventions, guards managed cleanup and records outcomes.
   It detects specific known storage/uv environment conflicts and applies
   job/variant run locks. Project implementations own their commands, Python packages and
   selected build tools, including input/output validation, shared-resource
   coordination, retry safety, recovery and any required isolation. They report
   success or failure according to their own contracts; PTK uses those outcomes
   for scheduling and reporting. PTK does not inspect or control arbitrary
   internal file and resource operations performed by project scripts.
   PTK supplies no general step input/output contract, file-access discovery,
   freshness tracking, artifact cache or filesystem/process/network sandbox.
   Repository-root cwd remains the default; changing cwd or providing separate
   directories does not restrict access to other locations.

   **Rationale:** Preserve flexibility for projects. Projects can reuse existing
   implementations, choose tools and languages, and define artifact, caching,
   isolation and recovery policies suited to their needs. PTK supplies common
   orchestration without imposing one build model or taking ownership of those
   project-specific semantics. This is an intentional division of responsibility,
   not an incomplete implementation of promised script monitoring or validation.

   **Alternatives considered:** Inferring dependencies from command text cannot
   account for arbitrary scripts and external resources. Requiring every project
   to adopt a universal I/O model, artifact tracker or mandatory sandbox would
   constrain integration and duplicate responsibilities of project-selected tools.
   Projects may provide such guarantees through their own implementation and
   execution tools where needed.

   **Consequences:** A needs edge waits for a prerequisite's accepted execution
   outcome; it neither transfers files nor checks their existence, freshness or
   correctness. continue_on_error can release a dependent without its artifacts.
   Separate folders and filtered environments do not prevent shared writes.
   Worker limits are not resource locks, and other invocations/processes can
   still access external resources. Retries can repeat side effects; cancellation
   and cleanup cannot roll back arbitrary writes or remote actions. --only-step
   leaves prerequisite outputs to the caller, without restoring historical
   artifacts. Commands must validate their inputs/results and coordinate shared
   state; callers needing isolation must supply an appropriate external boundary.

   **Presentation:** Guides, graph previews and reports must not imply automatic
   I/O dependency discovery, artifact correctness, race freedom or reproducible
   execution. Green nodes record the outcome reported by the project
   implementation. Documentation must explain project flexibility as the reason
   for this boundary and identify project implementation responsibility. The
   concrete responsibility table is in :ref:`execution-boundaries`.

   **Related requirements:** :need:`REQ_Sw_CONTROL`, :need:`REQ_Sw_ENVIRONMENT`,
   :need:`REQ_Sw_STEP_SELECTION`, :need:`REQ_Sw_GRAPH_INSPECTION` and
   :need:`REQ_Sw_REPORT_GRAPHS`.

.. ddec:: Target closure or explicit single-step execution
   :id: DD_PARTIAL_STEPS
   :status: accepted

   **Context:** A positional resume point is ambiguous in a dependency graph.

   **Decision:** Remove --from. --to STEP runs that target and its transitive prerequisites. --only-step STEP runs exactly the selected step, lists omitted prerequisites and leaves required existing artifacts to the user.

   **Alternatives considered:** A positional range and automatic restoration of historical outputs were rejected.

   **Consequences:** The options are mutually exclusive. Single-step execution can fail on a fresh checkout; normal validation and conditions still apply.

   **Related requirement:** :need:`REQ_Sw_STEP_SELECTION`.

.. ddec:: Make execution topology inspectable
   :id: DD_GRAPH_INSPECTION
   :status: accepted

   **Context:** Users need to understand dependencies before running project commands.

   **Decision:** Provide --graph on job/workflow execution routes and include graph previews automatically in dry-runs. Export an offline interactive HTML/SVG diagram plus a compact terminal dependency tree. Supply the same graph and tree projection to configuration navigation.

   **Alternatives considered:** Treating YAML order as a diagram or relying on an external diagram server was rejected.

   **Consequences:** Inspection alone does not prepare commands or resolve credentials/tools. Graph previews write only under .ptk/graphs; the presentation does not change scheduling. The detailed presentation and report decisions follow.

   **Related requirement:** :need:`REQ_Sw_GRAPH_INSPECTION`.

.. ddec:: Execution-direction trees with explicit shared references
   :id: DD_GRAPH_TREE
   :status: accepted

   **Context:** Dependency tables, artificial depth groups and a fixed four-column
   diagram obscure the relationships users need to inspect. A dependency graph
   can contain joins and is not necessarily a strict tree. Ninja's indented
   target inspection informed the tree view; Bazel's DOT output and Conan's HTML
   graph informed the retained graphical view. Sources: `Ninja targets and graph
   tools <https://ninja-build.org/manual.html#_extra_tools>`_, `Bazel graph output
   <https://bazel.build/query/language#graph>`_, and `Conan graph info
   <https://docs.conan.io/2/reference/commands/graph/info.html>`_.

   **Decision:** Use one domain graph description with unique nodes and all needs
   edges. Derive an ordered tree projection in Python in execution direction:
   nodes without prerequisites at the root, direct dependents as children, and
   each shared node expanded only on its first visit. Later occurrences are
   explicit leaf references. Both tree nesting and diagram arrows run from
   prerequisite to dependent. Terminal trees use Rich; VS Code renders the
   supplied projection and routes every occurrence to the same editable path.
   Workflow targets are secondary labels only when different from the invocation
   ID. Joins list all prerequisites; being displayed under one branch does not
   remove the other needs. Roots and siblings preserve authored order, and
   independent branches can overlap.

   **Changed decision:** The original target-first "depends on" direction put
   package above test and check. User feedback showed that this reads backwards
   when inspecting execution. All views now consistently show check → test →
   package, with independent work in separate branches. The needs model and
   scheduler semantics are unchanged; no alternate reverse-direction mode remains.

   **Alternatives considered:** Duplicating entire prerequisite subtrees can grow
   exponentially; discarding repeated edges misrepresents joins. Keeping depth
   buckets or inferring another graph in the extension was rejected.

   **Consequences:** Traversal is bounded by nodes plus edges and handles multiple
   independent roots. Terminal selection/skip annotations and single-step
   warnings remain explicit. The former table, depth groups and fixed-grid
   renderer are removed. Configuration interface version 5 replaces version 4
   because the tree parent/child semantics changed;
   older interfaces are rejected, with no compatibility parser.

   **Related requirement:** :need:`REQ_Sw_GRAPH_INSPECTION`.

.. ddec:: Bundle the layout engine for interactive offline diagrams
   :id: DD_GRAPH_LAYOUT
   :status: accepted

   **Context:** Join edges and wide graphs need a layout engine. Generated files
   must remain useful when copied to a machine without PTK or network access.

   **Decision:** Vendor the pinned Dagre browser bundle and its MIT notices with
   the Python package. Embed it and the shared viewer in each HTML file. Lay out
   unique nodes from prerequisites toward dependents; wrap full names and provide
   zoom, fit, pan, keyboard node activation and a dependency/result inspector.
   Respect light/dark themes and contain wide graphs in the canvas viewport.

   **Alternatives considered:** Installing Graphviz on every consumer machine,
   fetching scripts from a CDN and retaining the hand-positioned SVG were rejected.

   **Consequences:** HTML files are larger but self-contained. Interactive diagrams
   require JavaScript. No browser request or installed Node/Graphviz is needed.
   Dagre and its bundled graphlib remain third-party code whose version, source
   and local modification are recorded in graph_assets/README.txt. Package tests
   verify that wheel and sdist rebuilds retain these resources and licenses.

   **Related requirement:** :need:`REQ_Sw_GRAPH_INSPECTION`.

.. ddec:: Graphical dependency editing with recoverable validation
   :id: DD_GRAPH_EDITING
   :status: accepted

   **Context:** The report diagram makes joins clearer than a tree. Users want
   the same graphical overview while editing, selection dropdowns, and dragging
   that connects prerequisites. Configuration validation must not make the
   extension unusable when a project needs repair.

   **Decision:** Keep the sidebar for navigation and add a graphical canvas to
   job/workflow configuration forms. Reuse the pinned Dagre engine and license
   notices through a build-time copy from the report assets. Show one node per
   authored step or workflow invocation. Click a node or use the job/step
   dropdown to edit its fields. Drag from a prerequisite's bottom connector onto
   its dependent, or choose a prerequisite from a dropdown. Both actions add
   one explicit needs edge; named removal buttons remove one connection.
   Layout remains automatic, with prerequisite-to-dependent direction.

   **Identity and uniqueness:** Each repository/job pair may occur once within
   a workflow, even when parameters differ or dependencies would serialize the
   calls. Unqualified local and owner-qualified targets identify the same job;
   the same job name in another repository is distinct. Step IDs are unique
   within a job and prerequisite selections cannot repeat. Selectors exclude
   used choices; explicit YAML is subject to the same configuration validation.
   Jobs remain reusable across different workflows. This supersedes the earlier
   allowance for sequential repeated calls to one job.

   **Validation boundary:** Installed schema metadata marks graph fields.
   Client checks assist editing; they do not duplicate PTK's full configuration
   validation or substitute a bundled schema. The host checks requested edge
   changes against the current authored graph and existing source-version
   guards before writing. Cycles, self-links and duplicate additions are
   rejected without changing YAML. Invalid loaded graphs show a diagnostic
   while fields and Raw YAML remain available. Removal may repair missing or
   cyclic references incrementally. Other validation errors remain visible and
   do not prevent repair. Loop diagnostics are also refreshed when needs fields
   are edited, without waiting for a run. PTK still validates the whole project
   on reload/run.

   **Alternatives considered:** Reordering a list cannot represent joins and
   would obscure whether order or dependencies control execution. User feedback
   explicitly selected connecting dependencies. Free node positioning would
   introduce layout state unrelated to execution. Blocking the whole form on
   validation failure would prevent users from correcting their configuration.

   **Consequences:** Graph edits use the normal YAML editing/ownership path,
   preserving other prerequisites, comments and definition order. Keyboard
   dropdowns/buttons provide the same operations as dragging. No connection
   runs commands, transfers artifacts or changes project responsibility under
   :need:`DD_EXECUTION_BOUNDARIES`. The schema graph hint is an additive change;
   inventory version 4 and configuration version 5 retain their meaning.

   **Related requirement:** :need:`REQ_Sw_SCHEMA_AUTHORITY`.

.. ddec:: Collapsible report graphs preserve recorded evidence
   :id: DD_REPORT_GRAPHS
   :status: accepted

   **Context:** Users need to relate run outcomes to prerequisites, including
   shared steps, blocked chains and partial runs, without losing report overview.

   **Decision:** Embed the same diagram viewer in job and workflow HTML reports
   inside a native details disclosure, collapsed by default. Derive topology and
   outcomes from recorded step/job results, never reload current configuration to
   reconstruct them. Keep one node per invocation; include state text and colour,
   duration, reason, allowed-failure indication and workflow repository/job variant
   metadata. Keep the timeline for actual execution timing. The canonical job
   report model includes its graph so JSON export carries the same evidence.

   **Alternatives considered:** Linking only to a mutable preview file would lose
   portability and historical accuracy. Expanding every graph by default would
   obscure report totals. Removing report-disabled nodes would break their edges.

   **Consequences:** Layout is computed on first expansion. Reopening does not
   duplicate nodes, and reports remain single offline files. report: false keeps
   only the step ID and dependency edges as "Details hidden"; result, message,
   command, duration, logs and tool contributions remain excluded. Single-step
   reports retain omitted edges and the explicit bypass notice. No old renderer
   or graph reconstruction fallback is retained.

   **Related requirement:** :need:`REQ_Sw_REPORT_GRAPHS`.

.. ddec:: Independent variant selections with an explicit all action
   :id: DD_VARIANT_SELECTION
   :status: accepted

   **Context:** Jobs and workflows may need to run for several concrete variants.

   **Decision:** Keep selections per job/workflow in the extension, allow multiple/all variants, and automatically check the configured default when the selection is empty. Launch separate PTK tasks for each variant.

   **Alternatives considered:** A separate global Variants tree and a synthetic default checkbox were rejected.

   **Consequences:** Each task resolves parameters and workflow repository mappings independently. Workspace-owned workflows have no owner variant. CLI multi-variant batching remains a separate execution policy.

   **Related requirement:** :need:`REQ_Stkh_VARIANTS`.

.. ddec:: Import once and export from a canonical report model
   :id: DD_CANONICAL_REPORTS
   :status: accepted

   **Context:** Different exporters must not reinterpret the same tool evidence.

   **Decision:** Normalize tool results and log findings before exporting HTML, JSON, Markdown, JUnit or SARIF. Default report_formats to HTML and logging_history_backups to three.

   **Alternatives considered:** Independent per-exporter parsers were rejected.

   **Consequences:** Importer support bounds structured detail. Historical runs retain their context and evidence; absent findings do not prove success.

   **Presentation clarification:** Keep execution and imported test failure details
   in **What failed**, linking to expandable entries in the shared diagnostic
   view (:need:`DD_REPORT_EXPLORATION`).
   Pytest summary lines supply log findings when present; JUnit supplies test
   counts and detailed test results. Log occurrence counts stay separate because
   a test failure can appear in both sources. Suppression or disabling log
   analysis never removes execution or test failures. An empty analysis means
   no recognized diagnostics, not proof of a clean run.

   **Related requirement:** :need:`REQ_Sw_CANONICAL`.

.. ddec:: Keep severity separate from disposition
   :id: DD_LOG_DISPOSITIONS
   :status: accepted

   **Context:** Known diagnostic noise needs explanation without concealing execution failure.

   **Decision:** Retain warning/error severity, with active/ignored/justified disposition and reasons. Show occurrence counts, source log locations and filters on expandable diagnostic entries; exclude ignored and justified findings from the initial view. Use expandable evidence entries in the shared diagnostic view, with source
   labels and a separate failure recap (:need:`DD_REPORT_EXPLORATION`).

   **Alternatives considered:** Changing severity or making a failed process pass because its log message was ignored was rejected.

   **Consequences:** Users can reveal suppressed findings. Suppression does not change command exit status or imported test failures.

   **Related requirement:** :need:`REQ_Sw_LOG_POLICY`.

.. ddec:: Resolve runtime metadata lazily and distinguish PR commits
   :id: DD_RUNTIME_CONTEXT
   :status: accepted

   **Context:** PR checkouts can contain synthetic merge commits; unnecessary Git queries cost startup time.

   **Decision:** Resolve requested Git metadata at runtime and cache it for the invocation. Expose source and checkout commit separately, including short forms; an exact tag is empty when none exists.

   **Alternatives considered:** Always querying Git during editor discovery or treating the checkout SHA as the PR source SHA was rejected.

   **Consequences:** Context depends on the execution environment; the editor offers names and help without fetching values or credentials.

   **Related requirement:** :need:`REQ_Sw_PR_SOURCE`.

.. ddec:: Bundle matching package and extension with per-user setup
   :id: DD_DISTRIBUTION
   :status: accepted

   **Context:** Team members need one installation route and completion outside an activated environment.

   **Decision:** Carry the matching VSIX in the Python package. Installers set up the per-user executable and shell-specific completion profiles through self-service commands. Keep development editable and release artifacts prepared together.

   **Alternatives considered:** Requiring consumers to build the extension or enable completion on every terminal launch was rejected.

   **Consequences:** Completion is per-user but shell-specific; PATH selects the executable. Automatic keep-newer Python-package policy remains planned, not a claimed installer guarantee.

   **Related requirement:** :need:`REQ_Sw_BUNDLE_VSIX`.

.. ddec:: A project-discovering expert coordinates focused skills
   :id: DD_AUTHORING_AGENTS
   :status: accepted

   **Context:** Assistance must not bake PTK repository names and defaults into consuming projects.

   **Decision:** Use one PTK expert entry point with focused authoring, troubleshooting and log-analysis skills. Discover the actual project, installed CLI, permissions and supported contracts before acting.

   **Alternatives considered:** Adding agents solely for each skill was rejected as unnecessary coordination.

   **Consequences:** Specialists can be introduced for genuinely separate work later; a skill does not authorize executing or publishing unrequested project work.

   **Related requirement:** :need:`REQ_Sw_PROJECT_INDEPENDENCE`.

.. ddec:: Authored requirements and design records
   :id: DD_AUTHORED_RECORDS
   :status: accepted

   **Context:** Traceable requirements and decisions are needed without another runtime model loader.

   **Decision:** Author RST Sphinx-Needs requirements and ddec records following the supplied meta-model directive names, IDs and attributes. Configure the convention explicitly in Sphinx; do not load the reference YAML.

   **Alternatives considered:** Copying the old CLI specification or generating requirements from documentation preferences was rejected.

   **Consequences:** Requirements describe CLI product behavior, not extension UI or documentation authoring requests. Decision records explain tradeoffs and may discuss those supporting concerns.

.. ddec:: Component YAML declares choices; product variants select them
   :id: DD_COMPONENT_VARIANTS
   :status: accepted

   **Context:** The external reusable-component proposal declares features and
   selects values in CMake. Projects also use Make, Bazel and GN, and independent
   components may legitimately use the same local feature name.

   **Decision:** Keep the declaration in each registered component's PTK YAML.
   Identify a feature as component.FEATURE, with an uppercase local name. Product
   variants select those values using PTK's inheritance/default/constraint model.
   Export VARIANT_<COMPONENT>_<FEATURE>, VARIANT_COMPONENT_<COMPONENT> and
   VARIANT_NAME. Reject export collisions. Preserve typed enum strings instead of
   inventing numeric IDs from option order. Qualified substitutions are
   ${vh.features.component.FEATURE}; the environment adds VARIANT_COMPONENTS.

   **Alternatives considered:** Maintaining duplicate CMake and PTK declarations
   would create competing authorities. Globally unique feature names would couple
   reusable components unnecessarily. Implicit feature qualification and legacy
   export aliases would hide incomplete migrations.

   **Consequences:** Product selections, expressions, CLI overrides, completion
   and examples use qualified identities. The removed env export-prefix model,
   ``VH_*``/``BO_*`` names and unqualified feature selections have no compatibility path.
   Projects retain target/source/compiler mapping, including explicit numeric
   mappings where required. See :doc:`/guides/variant-generation` and
   :need:`REQ_Sw_COMPONENT_SELECTIONS`.

.. ddec:: Generators belong to the consuming step
   :id: DD_STEP_GENERATORS
   :status: accepted

   **Context:** A command or Python script needs variant inputs immediately
   before it runs. A shared mutable export folder can mix concurrent products.

   **Decision:** Add an ordered unique generators list to every step kind,
   including generation-only steps. Resolve once during preparation and pass a
   separate snapshot copy to each generator. Generate before every command or built-in operation
   attempt into the owning step's build directory; keep the default repository
   cwd. Validate returned paths/content/collisions before writes and atomically
   replace individual files. Unknown generators fail configuration validation; missing variants fail
   preparation. A generator failure stops that step before its command.

   **Alternatives considered:** The dedicated variant.generate builtin and
   arbitrary output override are removed. Generating at project load/editor
   discovery would create side effects during inspection. A single global file
   would allow concurrent variants to overwrite each other's configuration.

   **Consequences:** Dry-run/graph/skip/blocked paths do not generate. Retried
   commands regenerate inputs; generator exceptions themselves are not retried.
   No automatic cache or stale-output cleanup is introduced. Timeout/cancellation
   includes generation but cannot preempt synchronous trusted Python. Other steps
   use explicit paths and needs edges. Distinct variant/job/step identities have
   separate folders; overlapping runs of the same identity still share paths.
   CLI parallel variant scheduling remains a separate open requirement.
   See :need:`REQ_Sw_STEP_GENERATORS` and :need:`DD_EXECUTION_BOUNDARIES`.

.. ddec:: Use native build inputs and a project-owned Bazel adapter
   :id: DD_BUILD_ADAPTERS
   :status: accepted

   **Context:** Make/CMake/GN can include generated assignments. Bazel loads
   Starlark through labels and needs repository integration for a snapshot located
   in a PTK step folder. The user explicitly requested GN, not plain Ninja, and
   required any Bazel helper to live with the consuming project.

   **Decision:** Generate variant.mk, variant.cmake, variant.gni and versioned
   variant.bazel.json. CMake needs only include(); a project adapter may map values
   onto targets without redefining the feature model. Publish a downloadable
   Bzlmod repository-rule resource that reads Bazel JSON and exposes a constant
   dictionary plus typed settings for config_setting/select(). PTK runtime does
   not import or execute this resource. GN itself generates Ninja files.

   **Alternatives considered:** Loading an absolute external .bzl path as a Bazel
   label is not a valid integration. Mutating MODULE.bazel/BUILD files for each run
   or retaining CMake-owned selection would duplicate state. Bundling the helper
   as a PTK runtime builtin would violate project ownership.

   **Consequences:** Bazel gets one PTK configuration per invocation; projects use
   separate output bases and manage workspace symlinks/lockfiles/shared caches.
   The helper tracks snapshot content and repo_env, rejects unsupported schema
   versions, and does not expose command-line variant flags. Inactive non-boolean
   features have no typed setting. Projects own helper adaptation, supported Bazel
   versions and remote-build input staging. Tests verify actual consumers on the
   versions recorded in :doc:`/guides/variant-generation`; this is not universal
   tool/platform certification. See :need:`REQ_Sw_GENERATORS`.

.. ddec:: Use ordinary project tools instead of a third-party plugin API
   :id: DD_NO_PLUGIN_API
   :status: accepted

   **Context:** Python packages can expose commands and be distributed through
   Artifactory and executed with uv. PTK's six plugin hooks duplicate much of that
   integration while adding discovery, validation, dynamic service wiring and
   coupling to internal Python models and callback signatures. PTK has not been
   rolled out and has no external plugin consumers requiring compatibility.

   **Decision:** Remove all third-party step, generator, report-contributor,
   report-exporter, credential-provider and installer hooks. Remove the plugins
   and custom installers configuration fields, loader, registration machinery,
   plugin starter and authoring contract. Use a fixed schema-enumerated set of
   built-in operations/providers/formats. Project behavior runs as ordinary
   commands, including independently versioned Python CLI packages through uv.

   **Alternatives considered:** Retaining only selected plugin hooks would still
   require a public Python compatibility surface without a demonstrated need.
   Keeping migration code, a disabled/legacy loader, compatibility aliases or
   fallback behavior would preserve complexity with no installed user base to serve. Requiring every reusable tool to live in PTK's interpreter would
   retain dependency conflicts and unnecessary release coupling.

   **Consequences:** Built-in generators, supported result import/export, tool
   setup and credential providers remain. The editor consumes the updated schema
   and retains invalid documents for repair. Obsolete configuration fails rather
   than silently converting; installed old PTK entry points are inert. Internal
   dependency injection and built-in callbacks remain implementation details,
   not a third-party API. No automatic external generator or converter protocol
   is introduced. External tools own CLI/file contracts and their versions;
   PTK still versions its CLI, configuration, report and editor contracts. Project
   responsibility for side effects and outputs remains intentional for flexibility.

   **Related requirements:** :need:`REQ_Sw_EXTERNAL_TOOLS` supersedes
   :need:`REQ_Sw_PLUGINS`; :need:`REQ_Sw_NO_LEGACY` and
   :need:`REQ_Sw_SCHEMA_AUTHORITY` govern removal and editor recovery.
   See :doc:`/guides/python-tools`.

.. ddec:: Keep console step identity explicit and tool indentation local
   :id: DD_CONSOLE_CONTEXT
   :status: accepted

   **Context:** A step-only prefix is ambiguous when jobs or variants run
   concurrently. Prefixing only the first line of a multiline message loses
   context, and expanding tabs after adding the prefix shifts tool indentation.

   **Decision:** Use [variant][job][step] for console step records, and
   [variant][job] for job-level messages, matching the output folder order.
   Reuse the established default label
   for an absent variant. Prefix every logical line, expand tabs in tool text
   before adding the prefix, interpret ANSI styling and present carriage-return
   updates as separate lines without terminal cursor/erase operations.

   **Consequences:** Identifiers remain literal and unpadded. The terminal owns
   visual wrapping; very long lines can wrap to its left margin. Raw captured
   step logs and structured report identities remain unchanged. Workspace and
   cross-repository workflows qualify the job field as repository:job to
   distinguish equal IDs while retaining three fields. The workflow invocation
   alias belongs in header metadata and the summary.
   See :need:`REQ_Sw_CONSOLE_PREFIX` and :doc:`/guides/log-analysis`.

.. ddec:: Separate execution levels and give entity colors a consistent meaning
   :id: DD_RUN_HIERARCHY
   :status: accepted

   **Context:** Streaming output needs visible workflow, job and step boundaries,
   useful run metadata and consistent identity under concurrency. Colors in the
   terminal and extension should refer to the same execution entities.

   **Decision:** Use named start and summary boundaries with equals signs for
   workflows and dashes for jobs. Repeat [variant][job] or
   [owner-variant][workflow] in both titles and every metadata line. Workspace
   workflows use [workspace][workflow] because their jobs can have different
   variants. Use compact [variant][job][step] start/result lines without long
   step separators. These identities remain explicit under parallel output.
   Prefix report-link lines with that same owner identity and entity color.
   Preserve the workflow owner's variant in its saved report metadata so
   reopening the latest report cannot label it with today's variant selection.
   If that metadata is unavailable, identify the workflow without guessing a
   variant. Keep paths literal and child job identities repository-qualified
   whenever their run headers are qualified.
   Use purple workflows, cyan jobs and blue steps in CLI headings and extension
   entity views; use neutral gray for built-in extension commands. Keep outcome,
   warning, selection and focus colors independent. Exact shades follow the
   terminal/editor theme and text labels remain available without color.

   Keep entity titles in their own color, and color result labels separately:
   green PASSED, red FAILED, gray SKIPPED and amber CANCELLED. Color nonzero
   counts by status and leave zeros neutral. An allowed failure stays FAILED
   with an amber annotation, without changing the enclosing execution outcome.
   Named sections, per-item result/duration recaps and explicit outcome labels
   are the selected patterns; nested terminal boxes are unsuitable for live
   output that alternates between parallel jobs.

   Reuse prepared, masked project version and variant metadata; do not run extra
   discovery to decorate output. Workflow headers list actual participating
   repositories, versions and variants, without inventing a single workspace
   project version. Job headers include project/repository identity, project/PTK
   versions, variant description and counts, run ID and execution limits.
   Verbose console output and debug file logs include resolved variant details.
   Job summaries list steps; workflow summaries list qualified job identities,
   actual variants and invocation aliases. Both include durations, counts and
   reasons for skipped, blocked and allowed-failure cases. Execution failure
   recaps repeat complete step identities, or job identity if execution did
   not reach a step. Preserve failures permitted by step or invocation policy
   in the recap even when the parent passes. Detailed imported diagnostics
   remain in reports, with a report-findings marker for passed jobs when needed.

   Share presentation text with semantic roles between console and aggregate
   logs; only the console translates roles into colors. Write each complete
   header and summary block atomically and retain live interleaving of contextual
   records from concurrent jobs. Add an immutable workflow.log beside workflow
   reports; preserve per-job rotation and original raw per-step capture. Store
   raw logs under steps/STEP.log so a step named run cannot truncate run.log;
   do not reject valid IDs or add a special-name fallback. Declared log paths
   and report links follow the layout. Avoid nested indentation, padding
   streamed prefixes and terminal cursor rewriting.
   Align summary columns within each block without truncating identities.

   **Consequences:** Long lines can still wrap at the terminal margin. Concurrent
   output is identified by prefixes rather than assumed containment below the
   most recent heading. Aggregate human-readable log formatting changes; raw
   step capture and machine-readable event/result contracts remain available.
   This decision does not change project responsibility for script behavior or
   artifact validation (:need:`DD_EXECUTION_BOUNDARIES`). Other extension
   category colors remain pending a separate review. No migration or fallback
   presentation mode is introduced. See :need:`REQ_Sw_RUN_HEADERS`.

.. ddec:: Use one report structure and expand workflow jobs into recorded steps
   :id: DD_REPORT_EXPLORATION
   :status: accepted

   **Context:** Job reports placed extensive metadata before failures; workflow
   reports exposed less detail. Separate diagnostic presentations made it harder
   to trace a failure to its owner and evidence. Users requested a consistent
   report experience and expandable workflow graphs containing job steps.

   **Decision:** Use a shared offline HTML shell with compact run identity,
   linked counts, a failure recap, execution records, graph, timeline, diagnostics,
   tests, evidence and expandable configuration. Sticky navigation and stable
   anchors connect these views; following an evidence link reveals collapsed or
   filtered targets. Keep entity colors (purple/cyan/blue) independent from outcome
   colors. Show zero counts neutrally. Retain source, severity, disposition and
   ownership in one filterable diagnostic view, with active findings initially
   selected. Log occurrences never increment test totals or alter execution state.

   Save sanitized canonical child reports in the immutable workflow snapshot.
   Job containers expand to independent recorded step DAGs. Lay out each internal
   graph first and then size/layout the outer job DAG; connect inter-job edges to
   containers and internal edges only to their steps. This preserves scheduler
   semantics without inventing cross-job dependencies. Namespace presentation
   identities by invocation; preserve all joins and hidden-step topology. Use
   prepared topology labelled Not run when a job never reached execution, with
   its parent reason and masked metadata. Expand/collapse works by keyboard or
   pointer; each expansion fits the newly laid-out graph. Nodes, timeline rows
   and execution entries share navigation targets. Child reports link to their
   aggregate and retain captured evidence links.

   **Alternatives considered:** A test-only dashboard would obscure PTK's build,
   packaging and documentation jobs. Flattening jobs into a single step graph
   would misrepresent job readiness and confuse equal step names. Reading current
   YAML or fetching child reports in the browser would break historical fidelity
   and offline portability. Separate new reporting plugins would reintroduce the
   extension/versioning complexity rejected in :need:`DD_NO_PLUGIN_API`.

   **Consequences:** HTML is self-contained for viewing; linked evidence travels
   with its report directory. Embedding child snapshots increases workflow report
   size. Very large expanded graphs need zoom/pan; no automatic history comparison
   or flaky-test interpretation is added. JUnit/JSON/Markdown retain their existing
   roles; the new presentation does not change execution or artifact-validation
   contracts. Project implementations retain responsibility for outputs, side
   effects and isolation for flexibility (:need:`DD_EXECUTION_BOUNDARIES`).
   No legacy presentation mode or migration layer is introduced.

   **Related requirements:** :need:`REQ_Sw_REPORT_EXPLORATION`,
   :need:`REQ_Sw_REPORT_GRAPHS`, :need:`REQ_Sw_LOG_HTML`.

.. ddec:: Capture Sphinx evidence from build outputs and reuse report exporters
   :id: DD_SPHINX_EVIDENCE
   :status: accepted

   **Context:** Sphinx 9.1.0 and Sphinx-Needs 8.5.0 produce needs.json and
   schema_violations.json in documentation build outputs, outside PTK's log
   directories. Users need charts, tables and violations within the established
   job/workflow reports, plus access to successfully built documentation.

   **Decision:** Discover named JSON exports inside executed, report-visible
   step build directories after execution. Capture them and normalized data
   alongside the step's other report inputs so ordinary history retention and
   workflow snapshots preserve them. Read only the selected current_version,
   restore exported defaults when requested by the export, and preserve custom
   fields and nested validation reasons. Parse data without importing Sphinx,
   executing conf.py or adding runtime plugin hooks. Use the user-selected fixed
   limit of 100 MiB (104,857,600 bytes) per JSON file, independently for needs and
   violations exports. Accept the size boundary inclusively and report larger
   files as collection problems without changing execution status. This limit
   accommodates larger needs catalogs while retaining a finite input-size guard.

   Add a collapsible charts/table view to the existing offline HTML report,
   structured JSON and compact Markdown summaries. Use descriptive type and
   lifecycle-status distributions, with exact text counts and filtering; do not
   infer implementation completion. Qualify records by job, variant, step and
   source directory rather than merging equal need IDs. Present top-level schema
   findings in shared Diagnostics, using schema severity rather than console log
   level; errors also appear in What failed. Nested reasons remain part of one
   finding. Keep execution, imported tests, logs and schema findings distinct.

   Link to a recorded local documentation index only if the producing step
   passed and the index exists. Preserve structured evidence even when its step failed,
   but do not label that build successful. The documentation site itself stays
   in the project build output; PTK copies JSON evidence, not an entire website.

   **Alternatives considered:** Reading live build folders when opening old
   reports would replace historical evidence. Parsing only console logs would
   lose structured need fields and suppressed violations. Treating needs as test
   cases would distort JUnit and test totals. A new exporter plugin or Sphinx
   runtime dependency would add an unnecessary extension/versioning contract.

   **Consequences:** Report size grows with captured need fields and sources.
   The per-file limit is not an aggregate or process-memory budget: parsing,
   retained data and rendering can require more memory than the input file size.
   Missing exports mean unreported evidence, not successful validation. Site
   links can expire or point to a later rebuild; other builders and external URLs
   are not inferred. Projects retain ownership of stale-output cleanup,
   correctness, validation rules and traceability, preserving tool flexibility
   (:need:`DD_EXECUTION_BOUNDARIES`). See :need:`REQ_Sw_SPHINX_REPORTS`.

.. ddec:: Select two CMake importers using the producing executable
   :id: DD_CMAKE_REPORTS
   :status: accepted

   **Context:** Projects use different CMake generations. The report needs
   configuration evidence and warnings without treating negative feature probes
   as failed builds or using a previous successful configure after a failure.

   **Decision:** Use cmake-3.2 for 3.2 <= version < 4.1 and cmake-4.1 for >= 4.1.
   Detect a direct configure command's executable in the actual command environment
   and probe that executable. Prepare only its supported outputs. Use explicit
   capability gates inside the older importer, not a parser fallback selected by
   missing files. Changed caches provide producing-version provenance for indirect
   commands with artifacts beneath the step build directory. Document the supported
   invocation forms and unavailable evidence. Preserve process outcomes, bound inputs
   at 100 MiB each, mask retained data, capture current events/replies and keep immutable
   normalized snapshots. Reuse HTML/JSON/Markdown and the offline target graph viewer.
   Errors, developer/deprecation warnings and ordinary warnings share recorded
   diagnostic dispositions. Exact matching SARIF/console/log findings merge with
   contributing sources; uncertain matches remain source-labelled.

   **Consequences:** CMake 3.2 has less structured information. PTK requests its
   complete File API metadata set from 3.20. Wrappers and presets without explicit
   build paths must prepare structured outputs themselves. Probe negatives and
   optional packages never become failed tests. Profiling and compiler-specific
   build diagnostics are outside these configure importers. Project responsibilities
   in :need:`DD_EXECUTION_BOUNDARIES` remain. See :need:`REQ_Sw_CMAKE_REPORTS`.

.. ddec:: Generate dedicated diagnostics and open active errors locally
   :id: DD_DEDICATED_DIAGNOSTICS
   :status: accepted

   **Context:** A full execution report is useful evidence, but diagnosing a
   failure should immediately show findings from every importer in one focused view.

   **Decision:** Always generate a separate diagnostics.html alongside job exports
   and workflow aggregates, including when full report formats are empty. Share the
   full report's diagnostic projection and filters. Reuse ordered ignore/justify
   rules for all imported findings; retain severity/reason/source and factual
   process/test results. Local active errors always select the dedicated report,
   independent of open_report; CX and dry runs never open it. Workflow aggregate
   diagnostics suppress child openings. Warnings or suppressed findings alone do
   not trigger opening. Report-collection and actual execution errors remain visible.

   **Consequences:** This replaces the earlier policy that null disabled all local
   error-report opening. Full report export choices remain; always opens a full
   report on runs without active errors. Even an empty full-format list now produces
   diagnostics.html. Existing consumers keep original test outcomes and totals;
   diagnostic disposition is a separate interpretation. No browser failure changes
   a run's exit code. See :need:`REQ_Sw_DEDICATED_DIAGNOSTICS`.

.. ddec:: Import producing Bazel evidence through JSON BEP
   :id: DD_BAZEL_REPORTS
   :status: accepted

   **Context:** Bazel provides invocation, target, action and test evidence through
   BEP. Console output alone loses configuration identity, cache indicators and
   test-attempt relationships. Reading current tool versions or old build artifacts
   can misattribute a saved run; repeating test-target summaries as JUnit cases
   would inflate totals.

   **Decision:** Use one shipped JSON BEP importer and obtain the producing version
   from BuildStarted, including Bazelisk's selected version. Consume documented
   optional event fields rather than imposing unrelated major-version boundaries.
   Instrument supported direct build/test/coverage/run commands with a temporary
   JSON destination, preserving startup and forwarded arguments. Reuse explicit
   command-line destinations; an explicit empty path disables BEP. Document that
   the automatic destination overrides an implicit .bazelrc JSON destination.
   Capture changed conventionally named streams from wrappers without rewriting
   them, and accept report.import inputs. Never read stale build-tree evidence into
   a new invocation. Retain masked normalized snapshots per attempt and remove
   temporary raw files. Bound each artifact, captured console and normalized
   snapshot to 100 MiB, consistent with the other structured importers.

   Preserve configuration/aspect identity, test attempts/shards/runs, final target
   status, cache indicators and available metrics. Keep test-target totals separate
   from JUnit case totals. Merge exact diagnostic evidence with source labels and
   saved dispositions; retain uncertain matches explicitly. Full and dedicated
   job/workflow reports share diagnostics and local-only error opening. Preserve
   command exit codes, including a failing program after a successful bazel run
   build. Broken/incomplete streams are collection problems, not silent successes.

   Use native cquery JSON with configured dependency edges for a target-level
   overview. Replay canonical expanded options after direct invocations, preserve
   the execution context and verify top-level configuration checksums. Bound this
   extra analysis separately from execution; graph failure cannot change command
   outcomes. Omit files, configuration helper rules and toolchain internals; map
   generated files to producing rules and stop at external dependency boundaries.
   Preserve shared nodes and configuration identity. Only BEP target results
   supply execution states. Import paired cquery evidence without launching Bazel
   during report regeneration. Keep normalized graphs in immutable snapshots.

   **Consequences:** No Bazel/protobuf runtime dependency or BES service is added.
   JSON arrays, binary/text-protobuf BEP, arbitrary wrapper argument rewriting,
   remote artifact downloads and profile import are
   outside this importer. Artifact URIs remain references; local file links may
   expire. Action-event counts are not execution totals, and BEP event graphs are
   not target dependency graphs. Unknown optional events are ignored and missing
   metrics remain unavailable. The 100 MiB cap is not an aggregate memory budget.
   Native graph collection adds up to 60 seconds of analysis outside the command
   timeout; displayed graphs are bounded to 2,000 targets. Unsupported queries or
   incomplete builds have explicit graph availability, not invented dependencies.
   Projects retain artifact correctness and execution responsibilities under
   :need:`DD_EXECUTION_BOUNDARIES`. See :need:`REQ_Sw_BAZEL_REPORTS`.

Open boundaries
---------------

The intentional division of responsibility for project flexibility is recorded
in :need:`DD_EXECUTION_BOUNDARIES`. Project-specific script behavior, artifact
validation and recovery belong to the project implementation.
General input/output contracts, inferred file dependencies, artifact freshness or
correctness checks, content-addressed caching, enforced sandboxing, arbitrary
runtime step output values and automatic restoration of previous-run outputs are
not implemented by the dependency graph change. Nor is GitHub workflow generation.
These boundaries preserve project freedom to choose its tools and guarantees;
they do not represent a promise that PTK will take over script behavior. A
diagram or separate step folders do not change that responsibility. Future
proposals need their own decisions and verification.
Known planned product gaps remain in
:doc:`/requirements/decisions-and-gaps`.
