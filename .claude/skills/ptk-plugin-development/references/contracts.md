# PTK plugin authoring contracts

Use this reference when implementing a plugin. Read the installed configuration
schema and inspect the selected PTK version before changing a consumer project.
These Python interfaces are authoring material, not part of the published user
configuration reference.

## Registration

Install the plugin distribution in the same Python environment as PTK. The
project selects its distribution name in `plugins`; discovery never installs it.
Register callables in the distribution's `pyproject.toml`:

```toml
[project.entry-points."ptk.steps"]
"company.check" = "company_extension:check"

[project.entry-points."ptk.generators"]
custom = "company_extension:generate"
```

| Entry-point group | Callable contract |
| --- | --- |
| `ptk.steps` | `(step: PlannedStep, out, ctx: BuiltinContext) -> int`. Return an exit code, write messages with `out` for masking and poll `ctx.cancel.is_set()`. |
| `ptk.reporters` | `(report: Report, target: Path) -> Path`. Write the selected format and return its file. Select the entry-point name in `report_formats` or `-f`. |
| `ptk.report_contributors` | `(reports_dir: Path, labels: list[str]) -> list[Contribution]`. Read results only for the supplied visible step labels; disabled steps are filtered out. |
| `ptk.secret_providers` | `() -> SecretProvider`. Implement the secret-provider port. Use the entry-point name in `credentials.NAME.providers` and `--store`. |
| `ptk.installers` | `(tool_name: str, options: dict, out) -> None`. Raise `PtkError` on failure. Configure `tools.NAME.installers.PLUGIN: {options...}`. Plugin methods precede platform methods; PTK rechecks the configured version afterward. |
| `ptk.generators` | `(variant: ResolvedVariant) -> dict[str, str]`. Return relative filenames and text; PTK validates destinations and writes below the output folder. |

## Execution and failure handling

Only explicitly selected distributions are imported. Missing packages or entry
points, non-callable handlers and duplicate or reserved names are errors. Plugins
are trusted Python code, not sandboxed code.

Raise `PtkError` with actionable messages. Retries may invoke handlers again;
make them repeatable or leave retries disabled. Python handlers must cooperate
with cancellation; only subprocesses support forced process-tree termination.
Do not print secrets directly or include them in output files.

Custom step handlers receive the resolved run snapshot in `ctx.versions`;
consume that snapshot instead of rediscovering Git state during execution.

## Provider and installer behavior

Credential-provider keys include `storage_ref` as well as logical `ref`.
Persist by `storage_ref` to honor VMR namespaces. Provider availability checks
must be non-interactive; listing never calls `get` on persistent stores.

Installers must manage their own version-specific destinations and make binaries
discoverable through the configured environment/PATH. PTK cannot isolate
arbitrary external installer side effects.

## Integration checks

Use the bundled `examples/plugin` distribution as a minimal starter. Test its
installed entry points through a real configured job, including unselected
plugins, duplicate names, cancellation and failures. Declare and test the plugin's
supported PTK versions.
