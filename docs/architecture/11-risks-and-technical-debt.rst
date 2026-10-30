Risks and technical debt
========================

Open requirements and verification gaps
---------------------------------------

* Python-package downgrade protection remains unimplemented even though the
  request to keep the newer installation was agreed. See
  :need:`REQ_Sw_KEEP_NEWER_PACKAGE`.
* GitHub pipeline generation is draft roadmap work, not an available command.
* Implementation-derived requirements need stakeholder review. Existing tests
  provide candidate evidence, not automatic acceptance or certification.
* Native Windows, optional external tools and live artifact/credential services
  need their own verification environments. Local Linux results are insufficient
  for these boundaries.

Operational limits
------------------

* Job commands and installed plugins are trusted code; neither environment
  filtering nor the plugin allowlist is a sandbox.
* Shallow Git history and missing local PR head objects limit tag/version
  discovery. PTK does not fetch metadata to conceal this condition.
* Cooperative Python plugins can delay cancellation if they ignore the token.
  Subprocess termination has different capabilities.
* Cleanup is preflighted but not transactional. A later filesystem error can
  leave some output folders removed and others present.
* Per-user completion depends on profile loading and PATH. A shell selecting an
  older PTK can expose older completion data.
* Log recognition is deterministic and format-specific. Unknown diagnostics,
  multiline tool conventions and excluded/oversized files can limit findings.
  Original logs and report problems remain necessary evidence.

Variant integration boundaries
------------------------------

* Generated inputs do not prove that project scripts consumed them or produced
  correct artifacts. Projects own build mappings, validation and side effects to
  preserve implementation flexibility; see :need:`DD_EXECUTION_BOUNDARIES`.
* Distinct variant/job/step folders prevent cross-selection exports from sharing
  a path. Concurrent runs of the same identity and project-owned caches/output
  trees still require isolation or serialization by the project.
* Generator files are replaced individually. Interruption may leave a mixture of
  old/new files; failed steps do not launch their command, but external consumers
  must not read the folder concurrently. Removed generators do not clean stale
  files. Trusted generator plugins can have their own side effects.
* The Bazel helper is a project-owned Bzlmod resource. Native GN/Bazel tests are
  opt-in; absent tools mean unverified compatibility, not a passing native build.
  Exact format limits and integration examples are in
  :doc:`/guides/variant-generation`.

Documentation maintenance
--------------------------

Requirements retain stable IDs when moved or clarified. Superseded decisions
are marked obsolete rather than repurposing their IDs. Generated schemas prevent
field-reference drift, but behavioral guides and architecture still require
review when code changes. The archived old CLI and development plan are not
published, packaged, or loaded by the documentation build.
