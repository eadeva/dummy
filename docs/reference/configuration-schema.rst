Configuration reference
=======================

These tables describe YAML fields using the schema that PTK uses to validate
configuration. Section names are configuration paths: ``<name>`` means a key
you choose, and ``[]`` means a list item. Linked types lead to the corresponding
field table. Shared structures are documented once at their first path; the same
fields apply wherever that structure is linked, including nested step groups.

``Required: no`` means the field can be omitted. A missing default in a table
can mean a default factory (for example, an empty mapping), rather than ``null``.
Use ``ptk maintainer config show`` to inspect effective defaults for your project.

These tables describe the assembled model. Each conventional document contains
its section body; see :doc:`/guides/configuration` for file ownership and validation rules.
Built-in operation, generator, report and credential-provider choices are
validated by the schema. See :doc:`/reference/builtins` and
:doc:`/guides/python-tools` for project integration.

Export a machine-readable schema for editor integration::

   uv run ptk maintainer config schema -o schema.json

.. ptk-schema::
