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

   **Decision:** PTK standardizes variants, parameters, setup, credentials, execution, logging and reporting. Projects and plugins own the commands and domain-specific behavior. Workflow/job/step names follow GitHub terminology; PTK supports CX work beyond CI.

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

   **Alternatives considered:** Sequential/parallel groups and positional step lists were rejected.

   **Consequences:** Failures block dependent chains, independent branches continue, and tolerated failures remain visible. Workflows run locally; CX orchestration remains external.

   **Related requirement:** :need:`REQ_Sw_WORKFLOWS`.

.. ddec:: Jobs use the same dependency semantics for steps
   :id: DD_STEP_NEEDS
   :status: accepted

   **Context:** Steps can operate in separate output folders, and nesting limits useful concurrency.

   **Decision:** Use a flat steps mapping with explicit needs and one run or uses per node. Apply conditions, retries, timeouts and continue_on_error to individual steps. Reuse the bounded dependency scheduler.

   **Alternatives considered:** Keeping ordered lists, nested groups or a second background scheduling mechanism was rejected.

   **Consequences:** Authors must declare ordering. A skipped prerequisite blocks dependents, and limits on concurrent jobs and steps compose.

   **Related requirement:** :need:`REQ_Sw_CONTROL`.

.. ddec:: Keep the repository root as the default working directory
   :id: DD_ROOT_CWD
   :status: accepted

   **Context:** Many project commands expect paths relative to the repository.

   **Decision:** Retain repository-root cwd. Provide per-step build, log and report paths and explicit steps.ID path references; describe them as storage conventions, not an enforced sandbox.

   **Alternatives considered:** Changing default cwd to the step build folder was explicitly rejected.

   **Consequences:** Commands can write elsewhere. Authors must coordinate shared writes and external resources; PTK catches known uv environment conflicts but cannot infer arbitrary script behavior.

   **Related requirement:** :need:`REQ_Sw_ENVIRONMENT`.

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

.. ddec:: Target-first trees with explicit shared references
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
   edges. Derive an ordered, target-first tree projection in Python: final targets
   at the root, prerequisites as children, and each shared node expanded only on
   its first visit. Later occurrences are explicit leaf references. Both tree
   nesting and diagram arrows mean "depends on". Terminal trees use Rich; VS Code
   renders the supplied projection and routes every occurrence to the same
   editable configuration path. Workflow targets are secondary labels.

   **Alternatives considered:** Duplicating entire prerequisite subtrees can grow
   exponentially; discarding repeated edges misrepresents joins. Keeping depth
   buckets or inferring another graph in the extension was rejected.

   **Consequences:** Traversal is bounded by nodes plus edges and handles multiple
   disconnected final targets. Terminal selection/skip annotations and single-step
   warnings remain explicit. The former table, depth groups and fixed-grid
   renderer are removed. Configuration interface version 4 replaces version 3;
   older interfaces are rejected, with no compatibility parser.

   **Related requirement:** :need:`REQ_Sw_GRAPH_INSPECTION`.

.. ddec:: Bundle the layout engine for interactive offline diagrams
   :id: DD_GRAPH_LAYOUT
   :status: accepted

   **Context:** Join edges and wide graphs need a layout engine. Generated files
   must remain useful when copied to a machine without PTK or network access.

   **Decision:** Vendor the pinned Dagre browser bundle and its MIT notices with
   the Python package. Embed it and the shared viewer in each HTML file. Lay out
   unique nodes from targets toward prerequisites; wrap full names and provide
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

   **Related requirement:** :need:`REQ_Sw_CANONICAL`.

.. ddec:: Keep severity separate from disposition
   :id: DD_LOG_DISPOSITIONS
   :status: accepted

   **Context:** Known diagnostic noise needs explanation without concealing execution failure.

   **Decision:** Retain warning/error severity, with active/ignored/justified disposition and reasons. Show counts, source log locations and table filters; exclude ignored and justified findings from the initial table view.

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

Open boundaries
---------------

Enforced filesystem sandboxing, arbitrary runtime step output values, automatic
reuse of previous-run outputs and GitHub workflow generation are not implemented
by the dependency graph change. New proposals need their own decisions and
verification. Known planned product gaps remain in
:doc:`/requirements/decisions-and-gaps`.
