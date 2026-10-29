Architecture constraints
========================

PTK is a Python package requiring Python 3.12 or newer. Click supplies the CLI,
Pydantic supplies configuration validation and JSON Schema, and YAML is the
human-authored configuration format. Linux and Windows are exercised by CI;
PowerShell and Bash/Git Bash have explicit installation and completion paths.
A terminal emulator is not a completion provider: the active shell must load
its own profile hook.

Configuration has a fixed layout rooted at ``.main.ptk.yml``. The marker names
a repository-relative configuration directory. There is no recursive search for
arbitrary configuration fragments, include chain or legacy loading fallback.
Component feature declarations remain beside their component's source/build
files. See :doc:`/guides/configuration` for exact filenames.

Jobs execute local commands and trusted Python code with the user's permissions.
Environment filtering and plugin allowlists do not make them a sandbox.
Platform installers, external executables, network repositories and credentials
remain external dependencies. A configured tool can have platform-specific
requirements even when PTK itself runs on both platforms.

The requirements use the supplied directive names, attributes and relations as
an authoring convention. They do not load the reference meta-model. All authored
requirements use ``safety: QM``, ``security: false`` and ``legal: false``; these
are agreed classifications, not a claim that credential or path handling can
ignore normal engineering safeguards.

The documentation uses RST, Sphinx-Needs and the Read the Docs theme. The supplied
CSS controls width and table wrapping. Java, Doxygen, legacy custom extensions
and a meta-model loader are unnecessary for this site.
