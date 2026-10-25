Configuration reference
=======================

These tables are generated from the models used to validate configuration.
``Required: no`` means the field can be omitted. A missing default in a table
can mean a default factory (for example, an empty mapping), rather than ``null``.
Use ``ptk config show`` to inspect effective defaults for your project.

Loader directives such as ``include`` and YAML tags are processed before these
models. See :doc:`configuration` for loading, short forms and validation rules.
The presence of a field does not guarantee a planned integration is implemented:
``plugins`` is currently accepted but does not load entry points.

Export a machine-readable schema for editor integration::

   uv run ptk config schema -o schema.json

.. ptk-schema::
