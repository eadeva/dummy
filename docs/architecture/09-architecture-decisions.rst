Architecture decisions
======================

The following records summarize decisions established in the project discussion
and current implementation. They explain tradeoffs; the normative requirements
are in :doc:`/requirements/index`.

Fixed document ownership
------------------------

**Decision:** keep ``.main.ptk.yml`` and a known configuration directory layout;
place component variant definitions beside component code.

**Reason:** arbitrary recursive fragments and merge precedence made authoring
hard to predict. Fixed ownership supports diagnostics and editing without
requiring an include graph.

**Consequence:** filenames and locations are constrained. Configuration from the
older decentralized design must be rewritten; there is no migration fallback.

One loading and metadata authority
----------------------------------

**Decision:** PTK owns loading, validation, schemas and description metadata.
Integrations query the installed CLI.

**Reason:** a second loader in an editor can disagree with the executable version.

**Consequence:** generic additions are discoverable, while protocol changes still
require coordination. The extension is not dependent on JSON Schema alone.

Import once, export several formats
-----------------------------------

**Decision:** normalize supported tool outputs and diagnostic findings into a
canonical report model before export.

**Reason:** HTML, JSON, Markdown and other exporters should share interpretation.

**Consequence:** importer coverage limits the structured detail available.
Unrecognized logs remain raw evidence; no finding is not proof of success.

Per-user distribution
----------------------

**Decision:** prepare matching Python and editor artifacts together, carry the
VSIX in the Python package, and let installers call explicit self-service setup.

**Reason:** team members should not build the extension or configure completion
manually after every normal install.

**Consequence:** release preparation needs Node and documentation dependencies;
consumers do not. Shell profiles remain shell-specific and PATH chooses the CLI.

Requirements are authored documents
-----------------------------------

**Decision:** maintain RST Sphinx-Needs directives following the supplied
meta-model, with stakeholder, system and software levels.

**Reason:** traceability and consistent attributes are needed without introducing
another runtime schema loader or copying the old CLI's specification.

**Consequence:** the selected convention is explicitly configured and tested.
Future changes to the reference meta-model require intentional review of this
convention; they are not automatically applied.
