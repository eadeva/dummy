Running jobs in Docker
======================

``ptk --docker`` runs a job with the PTk installed in the project's Docker image.
The host PTk prepares the container, passes credentials and starts
``ptk run JOB`` inside it; the job is planned and executed by the image's PTk,
so ``os``, tool paths and conditions are those of the image.

The default is **on for Linux** when the project configures an image, and **off
on Windows**. Use ``--docker`` or ``--no-docker`` to choose explicitly, before the
job (``ptk --docker build``) or as a job/workflow option (``ptk build --docker``).
Inside the image ``--docker`` is never used again.

Configuration
-------------

The ``docker`` section belongs to ``project.ptk.yml``:

.. code-block:: yaml

   docker:
     image: artifactory.example.com/team-docker-local/build/project_build:1.0
     credential: artifactory_bdc     # user + token for docker login
     wsl_distro: Ubuntu-24.04        # Windows: Docker Engine in this WSL distribution
     workspace: sync                 # Windows: sync (WSL mirror) or mount (/mnt/c)
     env:                            # set in the container
       http_proxy: http://host.docker.internal:3128
     keep: [NO_PROXY]                # host variables passed by name
     run_args: []                    # extra docker run arguments

Jobs run in the image unless they set ``docker: false`` (for example Windows-only
tools). GUI jobs always stay on the host. Secret job parameters cannot be passed;
use step ``secrets`` instead.

The image must contain PTk and the job's tools on ``PATH``. Inside the image PTk
uses the container environment as baseline (``environment.isolate`` and
``inherit_path`` do not hide the image's ``PATH``), and tools with
``docker: false`` are only checked, never installed.

What happens
------------

#. On Windows PTk checks the WSL distribution and Docker Engine in it
   (``wsl -d DISTRO --exec docker ...``). Docker Desktop is not used.
#. ``docker login`` with the configured credential (password through stdin),
   then ``docker pull``.
#. **Windows, sync:** the repository is copied with ``rsync`` to
   ``~/.ptk/mirrors/<container>`` on the WSL disk. Output folders, ``.ptk`` and
   ``.venv*`` are excluded; symbolic links leaving the repository (for example a
   ``.git`` of a git-repo workspace) are copied as files.
   **Windows, mount** and **Linux:** the repository itself is mounted.
#. One container per repository (``ptk-<alias>-<hash>``) is kept running and
   reused. It is recreated when the image or the container settings change.
#. ``docker exec`` runs ``ptk run JOB`` with the selected variant, parameters and
   options. Step secrets are resolved on the host and passed by variable name;
   ``PTK_USER`` keeps the host user's credentials and role.
#. **Windows, sync:** ``_bin``, ``_logs``, ``_reports`` and the declared job
   outputs are copied back. ``_builds`` stays in WSL; PTk prints its
   ``\\wsl$`` path.
#. Reports open on the host as for local runs.

Workflows run each job in its repository's container.

Concurrency, locks and cancellation
-----------------------------------

* One ``ptk --docker`` invocation per repository at a time: a lock
  (``.ptk/docker.lock``) is held for sync, run and copy-back. A second invocation
  prints that it waits. A workflow takes the locks of all its repositories up
  front, in a fixed order, so two workflows cannot deadlock.
* Within a workflow, jobs of one repository run in parallel in the same container
  and mirror, with the same checks as on the host (no shared job folders or
  Python environments). Each job copies back only its own ``_bin``, ``_logs`` and
  ``_reports`` folders and declared outputs.
* A lock whose owner process no longer exists (crash, closed terminal) is removed
  automatically.
* Cancelling (Ctrl+C) returns 130 and releases the lock. Processes still running
  in the container are stopped (container restart) before the next run changes
  the workspace. In ``sync`` mode the job locks inside the mirror are reset at the
  same time; an interrupted sync or copy-back is completed by the next run.

Managing the container
----------------------

.. code-block:: console

   ptk self-service docker status
   ptk self-service docker stop
   ptk self-service docker remove

``remove`` keeps the WSL mirror, including ``_builds``.

Windows setup
-------------

#. ``wsl --install -d Ubuntu-24.04``
#. Install Docker Engine inside the distribution and add your user to the
   ``docker`` group.
#. Check it from Windows: ``wsl -d Ubuntu-24.04 --exec docker version``.
