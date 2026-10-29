Runtime view
============

Loading and command discovery
-----------------------------

1. The CLI captures invocation context and determines standalone or VMR routing.
2. Project discovery locates the marker within repository boundaries.
3. The loader reads conventional files and registered component documents,
   preserves provenance, and validates local and cross-document rules.
4. The driver exposes permitted jobs/workflows and their typed options.
   Validation can report a missing or broken project without requiring a job.

Job execution
-------------

1. Resolve requested variants, execution filters and parameter precedence.
2. Prepare paths, substitutions, environment, tools and credential requirements.
   A dry run previews the plan without executing steps or writing run reports.
3. Acquire the job/variant run lock and prepare current/history storage.
4. Execute ordered steps, nested groups and eligible background work. Apply
   configured timeouts, retries, conditional execution and failure policies.
5. Join background work at its defined boundary. Cancellation reaches active
   child processes; Python handlers must cooperate with the cancellation token.
6. Store the execution summary and captured report inputs, import contributions,
   export requested formats and apply the local report-opening policy.

The exact execution controls are documented in :doc:`/reference/execution`.
Report processing preserves execution status even when an importer fails or a
log finding is ignored. Independent selected variants can run in parallel;
a concurrent run targeting an already active job/variant fails with a lock diagnostic.

Local workflow execution
------------------------

The workflow planner resolves calls to concrete jobs and variants in their
owning repositories. Sequential groups wait for previous calls; parallel groups
share the configured concurrency limit, including nested groups. Failure and
cancellation policies govern queued calls. The workflow report retains child
results and logs so later runs do not replace its evidence. Local workflows are
rejected in CI; CI invokes jobs from its native pipeline.

Historical report export
------------------------

The report service selects a retained run, reads its stored execution context,
inputs and log-analysis policy, then writes the requested export. It does not
rerun the job. Current configuration changes therefore do not silently change
the meaning of a retained diagnostic decision.
