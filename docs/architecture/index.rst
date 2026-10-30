Architecture
============

Understand how PTK turns repository configuration into prepared runs and
traceable results. The CLI owns loading and execution metadata; external
integrations consume that interface. Application use cases coordinate the work,
domain rules describe behavior, and adapters perform I/O.

Three focused UML views explain the design: the system's building blocks,
the software dependency layers and the behavior of a job run. Each diagram
has editable PlantUML source beside its rendered view.

.. grid:: 1 1 3 3
   :gutter: 3

   .. grid-item-card:: Understand the boundaries
      :class-card: ptk-card ptk-blue
      :link: 03-system-scope-and-context
      :link-type: doc

      See the CLI's main building blocks and how they connect to project
      configuration, external functionality and run outputs.

   .. grid-item-card:: Understand the software layers
      :class-card: ptk-card ptk-teal
      :link: 05-building-block-view
      :link-type: doc

      Follow dependencies between drivers, application use cases, ports,
      adapters and domain rules.

   .. grid-item-card:: Follow an execution
      :class-card: ptk-card ptk-amber
      :link: 06-runtime-view
      :link-type: doc

      Compare rejected requests, previews and execution through to retained
      evidence, reports and the command's exit status.

The twelve arc42 chapters below describe the current CLI and its deployment
boundaries. Behavioral expectations and their review state are maintained in
:doc:`/requirements/index`. Configure these capabilities using the
:doc:`/reference/configuration-schema`.

.. toctree::
   :maxdepth: 1

   01-introduction-and-goals
   02-architecture-constraints
   03-system-scope-and-context
   04-solution-strategy
   05-building-block-view
   06-runtime-view
   07-deployment-view
   08-crosscutting-concepts
   09-architecture-decisions
   10-quality-requirements
   11-risks-and-technical-debt
   12-glossary
