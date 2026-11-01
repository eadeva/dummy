Configuration reference
=======================

These tables describe YAML fields using the schema that PTK uses to validate
configuration. Section names are configuration paths: ``<name>`` means a key
you choose, and ``[]`` means a list item. Linked types lead to the corresponding
field table. Shared structures are documented once at their first path; the same
fields apply wherever that structure is linked, including repeated job and step definitions.

``Required: no`` means the field can be omitted. A missing default in a table
can mean a default factory (for example, an empty mapping), rather than ``null``.
Use ``ptk maintainer config show`` to inspect effective defaults for your project.

These tables describe the assembled model. Each conventional document contains
its section body; see :doc:`/guides/configuration` for file ownership and validation rules.
Built-in operation, generator, report and credential-provider choices are
validated by the schema. See :doc:`/reference/builtins` and
:doc:`/guides/python-tools` for project integration.

Export a machine-readable schema for editor integration::

   ptk maintainer config schema -o schema.json

Ordinary users can inspect runtime document schemas with
``ptk describe --json --configuration``. Installed offline resources also include
``config-schema.json`` beside their README; the directive below is expanded only
in the published Sphinx site, so raw RST readers should use that JSON schema.

.. ptk-schema::
