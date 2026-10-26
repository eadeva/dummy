Preparing an Artifactory release
==================================

Run ``uv run ptk package`` (or ``ptk package`` from this checkout). The job
selects the uv ``release`` and ``docs`` dependency groups and creates::

   _bin/default/package/
     dist/ptk-VERSION-py3-none-any.whl
     dist/ptk-VERSION.tar.gz
     docs/ptk-VERSION-docs.zip
     SHA256SUMS
     manifest.json

Nothing is uploaded, tagged or version-bumped. No Artifactory endpoint or
credentials are needed. The version comes from PTK's project versioning
configuration in ``config/ptk/versioning/versioning.ptk.yml``. It is Git-managed:
reachable ``v*`` tags are selected and the ``v`` prefix removed. Exact clean
``v1.2.3`` becomes ``1.2.3``; commits after it add ``+N.gHASH`` and tracked dirty
changes add the configured ``dirty`` suffix. Fetch full history and tags for
release preparation. Untagged/shallow checkouts use the explicitly configured
``0.1.0.dev0`` development fallback; no release tag is created automatically.

The job consumes ``PTK_VERSION_PTK`` from its immutable run snapshot. Python
metadata normalizes that value to PEP 440 and rejects incompatible versions.
``pyproject.toml`` declares a dynamic version, so ordinary wheel/editable builds
also use PTK's configuration engine. Runtime ``ptk.__version__`` reads installed
distribution metadata. Source distributions freeze the resolved version in
``PKG-INFO``: rebuilding a wheel without Git retains the original version,
even inside another checkout or with a different build environment.

The job builds a source distribution and then the wheel from that archive,
using the build dependencies supplied by uv. It checks package metadata with
``twine check --strict``, installs the wheel without dependency downloads into
a temporary target, and runs the installed CLI in a separate consumer project.
That smoke test validates config creation and offline VS Code skill setup;
runtime dependencies come from the job's environment. It builds Sphinx HTML
with warnings treated as errors and computes SHA-256 checksums for the artifacts.

Only a previous unmodified output owned by this job is replaced. Build or
validation failures leave the previous successful artifacts intact. Additional
or modified files in the output directory are preserved by refusing replacement.

The wheel includes lightweight reference documentation, runnable example sources
and fourteen project authoring skills. It does not include rendered HTML or require
Sphinx at runtime. The full HTML documentation is the separate docs ZIP, suitable
for a documentation site or an Artifactory generic repository. Only the wheel and
source archive in ``dist`` belong in an Artifactory Python package repository.
See :doc:`editor` for installing version-matched offline skills and docs.
