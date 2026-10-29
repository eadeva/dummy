Requirements
============

The following pages contain the authored baseline and its traceability.

.. toctree::
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
   decisions-and-gaps

Scope and interpretation
------------------------

This baseline specifies the PTK CLI, installer/package boundaries and CLI-owned
integration metadata. It does not specify the VS Code extension's user interface.
Requirements were reconstructed from the project discussion and current code;
the older CLI's requirements are not copied into this baseline.

The hierarchy is **stakeholder → system → software**. Features cluster
stakeholder needs. System requirements describe a small set of external
contracts; software requirements refine observable CLI behavior. There is no
software-component requirement layer yet. Detailed design belongs in
:doc:`/architecture/index`.

Authoring convention
--------------------

The supplied meta-model is followed as an authoring convention, not loaded.
``docs/conf.py`` explicitly declares the selected Sphinx-Needs directive types,
attributes and relations. ``tests/test_documentation_requirements.py`` checks
that subset. The archived YAML is not a Sphinx or runtime dependency.

.. list-table:: Selected conventions
   :header-rows: 1
   :widths: 20 25 55

   * - Directive
     - ID prefix
     - Mandatory metadata and traceability
   * - ``feature``
     - ``FEAT_``
     - Organizational grouping; optional ``func_parent`` links another feature.
   * - ``req-stkh``
     - ``REQ_Stkh_``
     - ``req_type``, ``legal``, ``safety``, ``security``, ``status_crs``, ``safety_relevance``; exactly one ``clustered_by`` feature.
   * - ``req-sys``
     - ``REQ_Sys_``
     - ``req_type``, ``legal``, ``safety``, ``security``, ``status``, ``verification_criteria``, ``verification_level``; one or more ``req_satisfies`` links to stakeholder/system requirements.
   * - ``req-sw``
     - ``REQ_Sw_``
     - Same mandatory attributes as system requirements, with software verification-level values; one or more ``req_satisfies`` links to stakeholder/system/software requirements.

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
CI coverage and its limits are in :doc:`/ci/index`.

The generated ``needs.json`` exports these authored records and relations for
inspection. No generated data is loaded back as the authoring source.

Stakeholder overview
--------------------

.. needtable::
   :filter: type == "req-stkh"
   :columns: id;title;status_crs;tags;clustered_by
   :style: TABLE

System traceability
-------------------

.. needtable::
   :filter: type == "req-sys"
   :columns: id;title;status;tags;req_satisfies
   :style: TABLE

Software traceability
---------------------

.. needtable::
   :filter: type == "req-sw"
   :columns: id;title;status;tags;req_satisfies
   :style: TABLE
