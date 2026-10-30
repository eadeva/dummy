PTK — project tool kit
======================

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Documentation

   guides/index
   requirements/index
   architecture/index
   reference/index
   ci/index

.. container:: ptk-hero

   .. rubric:: Your project. One familiar CLI.
      :class: ptk-hero-title

   .. container:: ptk-lead

      A familiar command-line interface across projects, with shared conventions
      and the freedom to choose how each project works.

   PTK is a toolkit for standardizing how teams work with their projects:
   command discovery, variant handling, environment setup, credentials, logging
   and reporting. Projects define their own jobs in configuration and provide
   the actual functionality through tools, scripts and selected plugins.

   .. container:: ptk-actions

      .. button-ref:: /guides/getting-started
         :ref-type: doc
         :color: primary

         Run your first project

      .. button-ref:: /guides/configuration
         :ref-type: doc
         :color: primary
         :outline:

         Explore the configuration

   .. container:: ptk-hero-note

      Python 3.12+ · Windows and Linux · PowerShell and Bash / Git Bash

The idea
--------

A developer moving between projects should recognize how to discover commands,
select a variant, prepare tools, supply credentials and inspect a failed run.
PTK provides those shared conventions through a configuration-driven CLI.
Job names and options remain project-defined, with consistent help and completion.

The project owns what a command actually does. A build job can call CMake today
and a different tool tomorrow; a test job can delegate to a script or an installed
plugin. Those implementations can evolve while the team retains a familiar way
to invoke them and inspect their results.

PTK centralizes the repeated operational work and keeps project-specific
complexity with the project. That separation gives teams flexibility in their
tools, simpler daily usage and less duplicated setup, credential and reporting
logic. Start with one useful job around an existing command and add conventions
as the project needs them.

Workflows, jobs and steps
-------------------------

The names follow **GitHub Actions terminology** to make the structure familiar:
a workflow coordinates jobs, and each job contains steps.

.. list-table:: Three levels of project automation
   :header-rows: 1
   :widths: 15 50 35
   :class: tight-table

   * - Level
     - Responsibility
     - Example
   * - Workflow
     - Coordinate existing jobs sequentially or in parallel, including across repositories.
     - ``verify`` runs ``build``, then ``test`` and ``lint``.
   * - Job
     - Define a runnable task with parameters, a variant context, tool requirements and its own logs/reports.
     - ``build`` prepares and compiles a selected variant.
   * - Step
     - Run a command, script or built-in/plugin action; group steps when ordering or parallel execution is needed.
     - A ``compile`` step invokes the project's build tool.

Jobs also run directly, without a workflow. In PTK YAML, both workflows and jobs
use a ``steps`` list: a workflow entry calls a **job**, while a job entry defines
an executable **step** or a step group. The naming is familiar; PTK configuration
has its own schema.

PTK workflows currently orchestrate work locally. CX pipelines use their own
orchestration and invoke PTK jobs. See :doc:`guides/workflows` for the structure
in configuration and :doc:`architecture/06-runtime-view` for execution behavior.

Why teams use PTK
-----------------

.. grid:: 1 1 3 3
   :gutter: 3
   :class-container: ptk-benefits

   .. grid-item-card:: :octicon:`terminal` A CLI people can discover
      :class-card: ptk-card ptk-blue

      Jobs become commands with help, typed options and completion. Developers
      can inspect available choices and preview a run before executing it.

   .. grid-item-card:: :octicon:`git-branch` Variants without copied jobs
      :class-card: ptk-card ptk-teal

      Keep the job definition shared while selecting different features,
      components and data. Run one variant or several, with separate outputs.

   .. grid-item-card:: :octicon:`search` Evidence you can follow
      :class-card: ptk-card ptk-amber

      Find the command, step log, imported tool result and report for a run.
      Retained history helps explain what happened after the next run starts.

What you can do
---------------

.. grid:: 1 1 2 2
   :gutter: 3
   :class-container: ptk-capabilities

   .. grid-item-card:: :octicon:`play` Build, test and generate
      :class-card: ptk-card ptk-blue

      Run existing executables, shell commands and Python scripts as named
      steps. Declare inputs, conditions, timeouts, retries and parallel groups
      around the tools your project already uses.

      +++
      :doc:`Execution controls </reference/execution>` ·
      :need:`Related requirement <REQ_Sw_CONTROL>`

   .. grid-item-card:: :octicon:`git-branch` Model your product variants
      :class-card: ptk-card ptk-teal

      Describe features, component selections and constraints. Keep component
      definitions beside their code and run a job for several selected variants
      in parallel.

      +++
      :doc:`Configuration guide </guides/configuration>` ·
      :need:`Related requirement <REQ_Stkh_VARIANTS>`

   .. grid-item-card:: :octicon:`workflow` Compose local workflows
      :class-card: ptk-card ptk-blue

      Connect jobs into sequential or parallel workflows, including calls
      across independently configured repositories in a virtual monorepo.
      CX pipelines invoke jobs through their own orchestration.

      +++
      :doc:`Workflow guide </guides/workflows>` ·
      :need:`Related requirement <REQ_Sw_WORKFLOWS>`

   .. grid-item-card:: :octicon:`tools` Prepare the working environment
      :class-card: ptk-card ptk-teal

      Declare required tools, Python runtimes and credential providers.
      Compose job environments deliberately and use self-service commands for
      setup, diagnostics, completion and hooks.

      +++
      :doc:`Self-service commands </reference/cli>` ·
      :need:`Related requirement <REQ_Sw_ENVIRONMENT>`

   .. grid-item-card:: :octicon:`report` Understand failures and results
      :class-card: ptk-card ptk-amber

      Combine captured logs with JUnit, coverage and SARIF results. Review
      diagnostic severity, source logs and reasoned ignore/justify decisions
      in HTML, with other exports available from the same report model.

      +++
      :doc:`Logging and reporting </guides/log-analysis>` ·
      :need:`Related requirement <REQ_Stkh_LOG_ANALYSIS>`

   .. grid-item-card:: :octicon:`tag` Carry versions into your outputs
      :class-card: ptk-card ptk-blue

      Resolve project and component versions, generate version files and use
      runtime context in artifact destinations. Source Git identity remains
      distinct from the merge commit checked out by a PR pipeline.

      +++
      :doc:`Versioning guide </guides/versioning>` ·
      :need:`Related requirement <REQ_Sw_PR_SOURCE>`

   .. grid-item-card:: :octicon:`plug` Extend the shared toolkit
      :class-card: ptk-card ptk-teal

      Add trusted, explicitly selected Python plugins for steps, report
      formats, contributors, secret providers, installers and generators.
      Keep project-specific behavior in your project.

      +++
      :doc:`Plugin configuration </reference/plugins>` ·
      :need:`Related requirement <REQ_Sw_PLUGINS>`

   .. grid-item-card:: :octicon:`code` Bring the project into your editor
      :class-card: ptk-card ptk-blue

      Use the optional VS Code integration to browse configuration and run
      jobs. Synchronize the PTK expert agent and task-specific skills, with
      offline references matching the installed CLI.

      +++
      :doc:`Editor and authoring tools </guides/editor>` ·
      :need:`Related requirement <REQ_Sw_AGENT_SYNC>`

Who is PTK for?
---------------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Developers
      :class-card: ptk-card
      :link: guides/getting-started
      :link-type: doc
      :link-alt: Get started as a developer

      Discover the project's commands, select a variant and run a job with
      clear inputs. Use completion and reports to spend less time finding
      invocation details.

   .. grid-item-card:: Project maintainers
      :class-card: ptk-card
      :link: guides/configuration
      :link-type: doc
      :link-alt: Author your project configuration

      Capture repeatable work in conventional YAML files, keep component
      configuration close to its code and provide consistent defaults and
      authoring guidance for the team.

   .. grid-item-card:: CX and release engineers
      :class-card: ptk-card
      :link: ci/index
      :link-type: doc
      :link-alt: Understand CX and release preparation

      Invoke the same configured jobs from native pipelines. Select versions
      and environments explicitly, collect outputs and prepare artifacts
      using the project's release process.

   .. grid-item-card:: Test and quality engineers
      :class-card: ptk-card
      :link: guides/log-analysis
      :link-type: doc
      :link-alt: Inspect results and log diagnostics

      Follow failures back to their source logs, compare retained runs and
      record justified diagnostics while preserving the original execution
      and test outcomes.

Try a complete first run
------------------------

With PTK installed, create a small project that needs no compiler, credentials
or Git tags::

   ptk init my-project --name "My project" --config-dir config/ptk --yes
   cd my-project
   ptk --help
   ptk validate
   ptk hello --message "Hello from PTK"

The starter also includes debug/release variants and a build job. Continue with
:doc:`guides/getting-started` to preview a variant, run it and open its report.
When joining an existing project, start with ``ptk --help`` at its root.

Find your next step
-------------------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Learn and configure
      :class-card: ptk-card
      :link: guides/index
      :link-type: doc

      Practical guides for configuration, workflows, versions, reports,
      distribution and authoring tools.

   .. grid-item-card:: Look up exact behavior
      :class-card: ptk-card
      :link: reference/index
      :link-type: doc

      Command syntax, generated configuration fields, execution controls
      and plugin configuration.

   .. grid-item-card:: Understand the design
      :class-card: ptk-card
      :link: architecture/index
      :link-type: doc

      System boundaries, building blocks, runtime behavior and tradeoffs,
      organized into twelve architecture chapters.

   .. grid-item-card:: Integrate with CX
      :class-card: ptk-card
      :link: ci/index
      :link-type: doc

      The verification pipeline, package preparation and the boundary
      between preparing an artifact and publishing it.
