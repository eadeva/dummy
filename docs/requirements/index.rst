Requirements
============

.. toctree::
   :hidden:
   :maxdepth: 1

   stakeholder
   system
   software-configuration
   software-cli
   software-execution
   software-context
   software-integration
   software-reporting
   software-distribution
   traceability
   decisions-and-gaps

Explore what PTK is expected to do, how those expectations are refined, and
which decisions still need review. These are requirements for the CLI and its
installation/integration boundaries. Documentation layout, theme and authoring
instructions are maintained as guidance, not as product requirements.

.. grid:: 1 2 2 4
   :gutter: 2

   .. grid-item-card:: Current requirements
      :class-card: ptk-card ptk-metric

      .. container:: ptk-number

         :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags`

      All current lifecycle states, including planned work.

   .. grid-item-card:: Stakeholder needs
      :class-card: ptk-card ptk-metric

      .. container:: ptk-number

         :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and type == 'req-stkh'`

      The outcomes people need from PTK.

   .. grid-item-card:: System contracts
      :class-card: ptk-card ptk-metric

      .. container:: ptk-number

         :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and type == 'req-sys'`

      Observable behavior at external boundaries.

   .. grid-item-card:: Software behavior
      :class-card: ptk-card ptk-metric

      .. container:: ptk-number

         :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and type == 'req-sw'`

      Concrete CLI and execution rules.

.. container:: ptk-overview-note

   Counts are generated from the authored records. They count requirements,
   not independent features or passing tests. Superseded decisions are excluded
   from current totals and remain available in
   :doc:`decisions-and-gaps`.

From a need to observable behavior
----------------------------------

Features group stakeholder needs. System requirements describe the contracts
PTK exposes to people, shells, repositories and tools. Software requirements
refine those contracts into behavior that can be checked. Follow a requirement's
**Satisfies** links upward or **Satisfied by** links downward.

For example, follow :need:`REQ_Stkh_LOG_ANALYSIS` through
:need:`REQ_Sys_LOGS` to :need:`REQ_Sw_LOG_POLICY` and
:need:`REQ_Sw_LOG_FAILURES`.
The software requirement names the expected rule behavior, the verification
criteria and candidate evidence. Architecture explains how the design supports
that behavior; it does not replace the requirement.

Review state and implementation are different
---------------------------------------------

An accepted requirement may still be planned. An implemented behavior may still
need agreement on its requirement wording. Neither label means that verification
has passed on every target platform.

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Lifecycle — what has been agreed?
      :class-card: ptk-card ptk-blue

      .. list-table::
         :header-rows: 1
         :class: tight-table

         * - State
           - Current records
         * - Accepted
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and (status == 'accepted' or status_crs == 'accepted')`
         * - Under review
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and (status == 'under review')`
         * - New / changed
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and (status_crs == 'new/changed')`
         * - Draft
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and (status == 'draft')`
         * - In clarification
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and (status == 'in clarification' or status_crs == 'in clarification')`
         * - Deviation / rejection
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and (status == 'rejected' or status_crs in ['accepted with deviation', 'accepted with deviation agreed', 'rejected', 'rejected and not agreed'])`

      Stakeholder records use ``status_crs``; system and software records
      use ``status``. This view combines them without changing their meanings.

   .. grid-item-card:: Implementation — what exists today?
      :class-card: ptk-card ptk-teal

      .. list-table::
         :header-rows: 1
         :class: tight-table

         * - Coverage tag
           - Current records
         * - Implemented
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and 'implemented' in tags`
         * - Partial
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and 'partial' in tags`
         * - Planned
           - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and 'planned' in tags`

      These tags describe available behavior, not a verification percentage.
      Source and test links identify evidence to inspect; actual results
      depend on the checks and environments exercised.

Open work worth knowing about
-----------------------------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Accepted, not implemented
      :class-card: ptk-card ptk-amber

      Keeping a newer installed PTK Python package when an installer selects
      an older version remains outstanding. The extension's existing version
      protection is a separate behavior.

      +++
      :need:`Package downgrade protection <REQ_Sw_KEEP_NEWER_PACKAGE>`

   .. grid-item-card:: Callable GitHub templates
      :class-card: ptk-card ptk-amber

      Native GitHub templates and artifact Actions are implemented. Projects
      complete runner, Docker, caller-event and VMR checkout TODOs before use.

      +++
      :need:`Native CX generation <REQ_Sw_CI_GENERATION>`

Browse the specification
------------------------

.. grid:: 1 1 3 3
   :gutter: 3

   .. grid-item-card:: Stakeholder needs
      :class-card: ptk-card
      :link: stakeholder
      :link-type: doc

      Start with the intended outcomes and the feature groups that organize them.

   .. grid-item-card:: System contracts
      :class-card: ptk-card
      :link: system
      :link-type: doc

      Inspect CLI, shell, filesystem, tool and installation boundaries.

   .. grid-item-card:: Traceability explorer
      :class-card: ptk-card
      :link: traceability
      :link-type: doc

      Search and sort the records, follow parent links and find superseded decisions.

.. list-table:: Software requirements by area
   :header-rows: 1
   :class: tight-table
   :widths: 30 12 58

   * - Area
     - Current records
     - Questions it answers
   * - :doc:`Configuration and workspaces <software-configuration>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-configuration'`
     - How are files discovered, validated and owned? How are repositories routed?
   * - :doc:`CLI and completion <software-cli>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-cli'`
     - Which commands are exposed, and how do users discover options and values?
   * - :doc:`Execution and variants <software-execution>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-execution'`
     - How are runs prepared, scheduled, cancelled and cleaned up?
   * - :doc:`Runtime context and versions <software-context>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-context'`
     - Which values identify a run, its source and its versions?
   * - :doc:`Tools and integrations <software-integration>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-integration'`
     - How are tools, credentials, Python tools, generators and Git hooks connected?
   * - :doc:`Logging and reporting <software-reporting>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-reporting'`
     - How are results imported, retained, classified and exported?
   * - :doc:`Distribution and project authoring <software-distribution>`
     - :need_count:`type in ['req-stkh', 'req-sys', 'req-sw'] and not is_part and 'superseded' not in tags and docname == 'requirements/software-distribution'`
     - How are packages, editor artifacts, skills and offline references delivered?

Scope and evidence
------------------

This baseline covers PTK's CLI, installer/package behavior and CLI-owned
integration metadata. It does not specify the VS Code extension's user interface.
Requirements were reconstructed from the project discussion and current code;
the older CLI's requirements are not copied into this baseline.

The system layer is intentionally small. There is no software-component
requirement layer yet; detailed design belongs in :doc:`/architecture/index`.
Current CX coverage and its limits are documented in :doc:`/ci/index`.

Authoring convention
--------------------

The supplied meta-model is followed as an authoring convention.

All requirements have ``safety: QM``, ``security: false`` and ``legal: false``.
Stakeholder requirements also have ``safety_relevance: no``. These are the agreed
classifications, not evidence of verification. IDs remain stable when text is
clarified or moved. A replaced requirement becomes obsolete; its ID is not reused.

Status and evidence
-------------------

* ``accepted`` records an explicit agreed request; it does not claim completion.
* ``new/changed`` (stakeholder) and ``under review`` (system/software) identify
  reconstructed formulations that have not been explicitly accepted.
* ``draft`` identifies a proposal whose behavior/acceptance criteria need review.
* ``obsolete`` preserves a superseded decision without making it current.
* ``in clarification``, rejection and deviation states retain their supplied
  meanings and are available when an actual review decision warrants them.

Implementation coverage is a separate tag: ``implemented``, ``partial``,
``planned`` or ``superseded``. Each requirement identifies its origin and current
coverage. Source/test paths are candidate evidence; they are not a statement
that those tests passed on every operating system or that stakeholder acceptance
has occurred. Verification criteria describe what must be demonstrated. Current
CX coverage and its limits are in :doc:`/ci/index`.
