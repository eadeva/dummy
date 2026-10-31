CX setup matrix
===============

Use ``ptk maintainer matrix`` in the first GitHub workflow job to export the
selected project's execution and upload metadata. The helper is optional,
built into PTK, hidden from help/completion/editor command lists, and available
to local maintainers or automatically detected CX. CX access grants no other
maintenance rights and does not expose restricted jobs to ordinary users.

Commands
--------

Export JSON, select variants/jobs, or publish GitHub step outputs::

   ptk maintainer matrix
   ptk -V debug,prod maintainer matrix --job build --job package
   ptk maintainer matrix --format github >> "$GITHUB_OUTPUT"

All concrete variants are included by default; aliases are canonicalized and
deduplicated. Jobs respect audience, ``only_cx``, ``only_variants`` and
``omit_variants``. Invalid selected variants fail export. Projects without
variants use ``variant: null``. Step conditions, tools and required parameters
are checked when jobs run. Run from a Git checkout for source commit identity.

From a VMR root use ``ptk firmware maintainer matrix`` for that member. Exported
commands execute from the selected repository root. There is no workspace-wide
aggregation. Use the same checkout/configuration in setup and execution jobs.
``--set`` is rejected; workflow steps can append required execution parameters.

Minimal JSON contract
---------------------

The document contains ``schema_version: 1``, ``matrix: {include: [...]}`` and
``upload_base``. Each row contains:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Meaning
   * - ``repository``
     - Owning repository alias.
   * - ``variant``, ``aliases``
     - Canonical variant and its aliases; null and an empty list without variants.
   * - ``job``, ``command``
     - PTK job name and argv, such as ``["ptk", "-V", "debug", "run", "build"]``.
   * - ``version``
     - Discovered project version for this variant/job; null when versioning is unconfigured.
   * - ``commit``
     - Full source commit, including the PR head rather than GitHub's synthetic merge commit.
   * - ``upload``
     - Configured Artifactory ``url``, ``repository``, ``path``, ``base_url`` and ``base_path``; null when unconfigured.

``upload_base`` contains the shared Artifactory ``url``, ``repository`` and
``path``: base path plus event route, before the job suffix. It is null when
unconfigured, empty, or different between selected rows; each row's ``upload``
still supplies its own base. See :doc:`artifacts` for routing. Dates use one
invocation timestamp; ``--event EVENT`` and timezone-aware ``--at`` support
routing previews. A local maintainer can add ``--ci`` to include CX-only jobs.

Output paths are deliberately absent. They belong to the completed producer
job, where runtime values are known. Existing :doc:`output-reuse` declarations
and their runtime substitutions are unchanged. Matrix export does not resolve
or reject a job's runtime-dependent output paths. It does not execute jobs,
install tools or transfer artifacts; configured version-discovery commands may
run to resolve versions and destinations.

Inputs come from GitHub needs
------------------------------

``needs: [build]`` identifies ``build`` as the producer whose artifacts the
consumer needs to download. **There is no separate PTK inputs declaration.**
Keep GitHub producer job IDs aligned with PTK job names, or translate them in
the project's transfer script when using different IDs. The setup job is a
metadata dependency, not an artifact producer.

After execution the producer selects the actual files and uploads them with
these lookup properties. The downstream job searches below the shared upload
base, using its GitHub ``needs`` to supply the producer job name:

.. list-table:: Artifact property contract
   :header-rows: 1
   :widths: 25 75

   * - Property
     - Value
   * - ``version``
     - Producer version; the matrix supplies it when configured.
   * - ``commit``
     - Producer source commit from the matrix.
   * - ``variant_alias``
     - The upload manifest supplies the canonical variant and all configured aliases, or default without variants. Select the desired producer alias when downloading.
   * - ``job``
     - Producing PTK job, selected by the consumer's GitHub ``needs``.
   * - ``step``
     - Step inside the producing job that created the artifact.
   * - ``artifact_type``
     - Optional discriminator such as ``binaries``, ``symbols`` or ``report``, especially when one step produces multiple artifacts.

For example, artifacts from ``build/compile`` can share version, commit and
variant while using ``artifact_type=binaries`` or ``artifact_type=symbols``.
A test job depending on ``build`` can select only the binaries. Completed jobs
write an :doc:`upload manifest <artifacts>` with actual paths, producing steps
and optional output ``artifact_type`` labels. The shipped Actions own property assignment, matching, ZIP packaging and
downloads; projects may also supply their own transfer steps. A type
can group several files; it need not equal a filename extension. Do not select
an arbitrary artifact if the supplied properties match several candidates.

Generated GitHub workflows
--------------------------

Use ``ptk maintainer gen-workflows`` to create callable workflows. Their setup
job calls ``ptk maintainer matrix --workflow NAME --format github`` to export
per-invocation matrices and producer selectors. Every execution job depends on
setup and its configured producers. See :doc:`github-actions` for the shipped
upload/download/run Actions, Docker/VMR TODOs and full contracts.
