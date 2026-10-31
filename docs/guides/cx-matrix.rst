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
     - Agreed producer variant alias; use the canonical name when there is no alias, or ``default`` without variants. Use the same choice for upload and download.
   * - ``job``
     - Producing PTK job, selected by the consumer's GitHub ``needs``.
   * - ``step``
     - Step inside the producing job that created the artifact.
   * - ``artifact_type``
     - Optional discriminator such as ``binaries``, ``symbols`` or ``report``, especially when one step produces multiple artifacts.

For example, artifacts from ``build/compile`` can share version, commit and
variant while using ``artifact_type=binaries`` or ``artifact_type=symbols``.
A test job depending on ``build`` can select only the binaries. Step and type
are uploader/consumer metadata, not predicted output paths or new PTK fields.
Projects own property assignment, matching, packaging and downloads. A type
can group several files; it need not equal a filename extension. Do not select
an arbitrary artifact if the supplied properties match several candidates.

GitHub workflow setup
---------------------

``--format github`` prints exactly three single-line outputs: ``matrix`` and
``upload_base`` as compact JSON, and ``has_jobs`` as ``true``/``false``. This
example selects one build per variant. Add the project's checkout, Python, PTK
and tool installation steps where indicated. The ``ci/*.py`` transfer scripts
are project-owned examples, not commands shipped by PTK.

.. code-block:: yaml

   jobs:
     setup:
       runs-on: ubuntu-latest
       outputs:
         matrix: ${{ steps.ptk.outputs.matrix }}
         upload_base: ${{ steps.ptk.outputs.upload_base }}
         has_jobs: ${{ steps.ptk.outputs.has_jobs }}
       steps:
         # Add checkout and PTK installation.
         - id: ptk
           run: ptk maintainer matrix --job build --format github >> "$GITHUB_OUTPUT"

     build:
       needs: setup
       if: needs.setup.outputs.has_jobs == 'true'
       runs-on: ubuntu-latest
       strategy:
         matrix: ${{ fromJSON(needs.setup.outputs.matrix) }}
       steps:
         # Add the same checkout, PTK and required tools.
         - name: Execute producer
           env:
             PTK_COMMAND: ${{ toJSON(matrix.command) }}
           shell: python
           run: |
             import json, os, subprocess
             subprocess.run(json.loads(os.environ['PTK_COMMAND']), check=True)
         - name: Upload completed outputs with properties
           env:
             PTK_MATRIX_ROW: ${{ toJSON(matrix) }}
             PTK_UPLOAD_BASE: ${{ needs.setup.outputs.upload_base }}
           run: python ci/upload_artifacts.py

     test:
       needs: [setup, build]
       if: needs.setup.outputs.has_jobs == 'true'
       runs-on: ubuntu-latest
       strategy:
         matrix: ${{ fromJSON(needs.setup.outputs.matrix) }}
       steps:
         # Add checkout and the project's transfer tooling.
         - name: Download artifacts from needed producers
           env:
             PTK_NEEDS: ${{ toJSON(needs) }}
             PTK_MATRIX_ROW: ${{ toJSON(matrix) }}
             PTK_UPLOAD_BASE: ${{ needs.setup.outputs.upload_base }}
             PTK_PRODUCER_STEP: compile
             PTK_ARTIFACT_TYPE: binaries
           run: python ci/download_artifacts.py

The download script reads producer names from ``PTK_NEEDS`` (excluding
``setup``), and combines them with version/commit/variant and the chosen
producer step/type. The upload script receives actual output paths from the
completed job and assigns those same properties. Authentication, archive
layout and restoration remain in these scripts. If versioning is unconfigured,
choose the project's version policy rather than treating null as a real version.

Pass argv through JSON as shown, rather than joining it into a shell command.
Retain setup's resolved upload base instead of recomputing timestamped routes
in later jobs. This is optional help for initial workflow setup; GitHub owns
dependencies and automatic workflow-file generation remains a separate proposal.
