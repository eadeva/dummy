Configuration reference
=======================

These tables are generated from the models used to validate configuration.
``Required: no`` means the field can be omitted. A missing default in a table
can mean a default factory (for example, an empty mapping), rather than ``null``.
Use ``ptk setup config show`` to inspect effective defaults for your project.

These tables describe the assembled model. Each conventional document contains
its section body; see :doc:`configuration` for file ownership and validation rules.
``plugins`` selects installed distributions for entry-point loading; see
:doc:`plugins` for the extension contracts and configuration examples.

Export a machine-readable schema for editor integration::

   uv run ptk setup config schema -o schema.json

.. ptk-schema::
