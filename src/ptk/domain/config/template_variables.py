"""PTK-owned template catalogue and field capabilities, without runtime values."""

from .dates import DATE_FIELDS

PROJECT_KEYS = {"name", "root", "description", "alias"}
RUN_KEYS = {
    "id",
    "job",
    "variant",
    "step",
    "build_dir",
    "bin_dir",
    "log_dir",
    "reports_dir",
}
VH_KEYS = {"variant", "aliases", "components", "component_list", "features", "data"}
GIT_FIELDS = {
    "branch": "Source branch; PR head branch in GitHub Actions, empty for a detached local HEAD.",
    "commit": "Full source commit; PR head SHA instead of GitHub's merge/base SHA.",
    "short_commit": "First 12 hexadecimal characters of the source commit.",
    "checkout_commit": "Full commit actually checked out; may be a synthetic PR merge.",
    "short_checkout_commit": "First 12 hexadecimal characters of the checkout commit.",
    "tag": "Exact source-commit tag; empty if none. Triggering tag, otherwise first sorted tag.",
    "tags": "Sorted list of all locally available exact tags on the source commit.",
    "dirty": "Whether the checkout has tracked changes; untracked files are excluded.",
}
GITHUB_FIELDS = {
    "event_name",
    "ref_name",
    "ref_type",
    "sha",
    "run_id",
    "run_attempt",
    "repository",
    "event.pull_request.number",
    "event.release.tag_name",
    "event.release.prerelease",
}
CONTEXTS = ["vars", "default", "environment", "job", "step", "secret", "destination"]


def annotate_schema(schema):
    """Mark only values the runtime actually substitutes, including named steps."""
    defs = schema["$defs"]
    schema["properties"]["vars"]["x-ptk-template-context"] = "vars"
    for definition, fields in {
        "EnvironmentSpec": {
            "set": "environment",
            "path_prepend": "environment",
            "path_append": "environment",
        },
        "JobSpec": {"env": "job", "outputs": "job"},
        "ParamSpec": {"default": "default"},
        "StepSpec": {
            "run": "step",
            "cwd": "step",
            "with": "step",
            "env": "secret",
            "outputs": "step",
        },
    }.items():
        for name, context in fields.items():
            defs[definition]["properties"][name]["x-ptk-template-context"] = context
    schema["properties"]["artifactory"]["x-ptk-template-context"] = "destination"


def catalogue(value, environment_names=()):
    """Expose names/descriptions, never environment, credential or resolved values.

    Accept partially invalid authored data so validation errors do not disable
    completion while the user repairs a configuration.
    """

    def mapping(item):
        return item if isinstance(item, dict) else {}

    value = mapping(value)
    entries = {}

    def add(reference, group, description, contexts=CONTEXTS, **extra):
        entries[(reference, extra.get("job"))] = {
            "reference": reference,
            "group": group,
            "description": description,
            "contexts": contexts,
            **extra,
        }

    def paths(item, prefix):
        for key, child in mapping(item).items():
            if not isinstance(key, str) or "." in key:
                continue
            name = f"{prefix}.{key}"
            yield name
            yield from paths(child, name)

    for key in sorted(PROJECT_KEYS):
        add(
            f"project.{key}",
            "Project",
            {
                "root": "Absolute project directory.",
                "name": "Project display name.",
                "alias": "Repository alias.",
                "description": "Project description.",
            }[key],
        )
    for key, description in GIT_FIELDS.items():
        add(
            f"git.{key}",
            "Git",
            description,
            availability="Resolved at runtime; requires Git.",
        )
    for key in sorted(RUN_KEYS):
        contexts = (
            ["job", "step", "secret"]
            if key == "step"
            else ["vars", "environment", "job", "step", "secret"]
        )
        if key in {"job", "variant"}:
            contexts = [*contexts, "destination"]
        add(
            f"run.{key}",
            "Run",
            {
                "id": "Unique run identifier.",
                "job": "Current job name.",
                "variant": "Selected variant, or default.",
                "step": "Current step path.",
                "build_dir": "Build directory; step-specific inside steps.",
                "reports_dir": "Reports directory; step-specific inside steps.",
                "bin_dir": "Job binary output directory.",
                "log_dir": "Job log directory.",
            }[key],
            contexts,
            availability="Resolved when the job runs.",
        )
    for prefix in ("date", "date.utc"):
        for key in sorted(DATE_FIELDS):
            add(
                f"{prefix}.{key}",
                "Date",
                f"Invocation {key.replace('_', ' ')} in {'UTC' if prefix.endswith('utc') else 'local time'}.",
            )
    add(
        "env:NAME",
        "Environment",
        "Environment variable; enter its name.",
        placeholder="NAME",
    )
    add(
        "env:NAME:-fallback",
        "Environment",
        "Fallback when the environment variable is absent.",
        placeholder="NAME",
    )
    names = set(environment_names)
    names.update(mapping(mapping(value.get("environment")).get("set")))
    names.update(
        {
            "PTK_PROJECT",
            "PTK_PROJECT_ROOT",
            "PTK_JOB",
            "PTK_RUN_ID",
            "PTK_VARIANT",
            "PTK_BIN_DIR",
            "PTK_LOG_DIR",
            "PTK_REPORTS_DIR",
        }
    )
    for job in mapping(value.get("jobs")).values():
        names.update(mapping(mapping(job).get("env")))
    for name in sorted(
        n
        for n in names
        if isinstance(n, str) and n and not any(c in n for c in "{}:\r\n")
    ):
        generated = name.startswith("PTK_") and name not in environment_names
        add(
            f"env:{name}",
            "Environment",
            "Environment variable; value is never previewed.",
            ["job", "step", "secret"] if generated else CONTEXTS,
            availability="Must be defined in the execution environment.",
        )
    for name in paths(value.get("vars"), "vars"):
        add(name, "Variables", "Configured variable; resolved at runtime.")
    for job_name, job in mapping(value.get("jobs")).items():
        for step_name in mapping(mapping(job).get("steps")):
            for field in ("build_dir", "reports_dir", "log_file"):
                add(
                    f"steps.{step_name}.{field}",
                    "Steps",
                    f"Current-run {field.replace('_', ' ')} for step {step_name}. Declare needs when consuming its files.",
                    ["job", "step", "secret"],
                    job=job_name,
                )

        for name, spec in mapping(mapping(job).get("params")).items():
            secret = mapping(spec).get("type") == "secret"
            add(
                f"params.{name}",
                "Parameters",
                "Current job parameter."
                if not secret
                else "Secret parameter; step environment only.",
                ["secret"] if secret else ["job", "step", "secret"],
                job=job_name,
            )
    variants = mapping(value.get("variants"))
    if variants:
        contexts = [c for c in CONTEXTS if c != "destination"]
        for key in ("variant", "aliases", "component_list"):
            add(f"vh.{key}", "Variants", "Selected variant metadata.", contexts)
        for name, component in mapping(variants.get("components")).items():
            add(
                f"vh.components.{name}",
                "Variants",
                "Whether the component is active.",
                contexts,
            )
            for feature in mapping(mapping(component).get("features")):
                add(
                    f"vh.features.{name}.{feature}",
                    "Variants",
                    "Resolved feature value.",
                    contexts,
                )
        for variant in mapping(variants.get("variants")).values():
            for name in paths(mapping(variant).get("data"), "vh.data"):
                add(
                    name,
                    "Variants",
                    "Custom variant data.",
                    contexts,
                    availability="Must exist in the selected variant.",
                )
    versioning = mapping(value.get("versioning"))
    if versioning:
        prefixes = ["version.current"]
        alias = mapping(value.get("repository")).get("alias") or mapping(
            value.get("project")
        ).get("name")
        if alias:
            prefixes.append(f"version.projects.{alias}")
        dependencies = set(mapping(versioning.get("dependencies")))
        for job in mapping(value.get("jobs")).values():
            dependencies.update(mapping(mapping(job).get("version_dependencies")))
        prefixes.extend(f"version.projects.{alias}" for alias in sorted(dependencies))
        for prefix in prefixes:
            add(
                f"{prefix}.variant",
                "Versions",
                "Variant used to discover this repository's version.",
            )
        component_names = set(mapping(versioning.get("components"))) | set(
            mapping(variants.get("components"))
        )
        prefixes += [
            f"{prefix}.components.{name}"
            for prefix in prefixes[:2]
            for name in sorted(component_names)
        ]
        for prefix in prefixes:
            for field in (
                "value",
                "raw",
                "source",
                "major",
                "minor",
                "patch",
                "prerelease",
                "build_metadata",
                "sort_key",
                "git.commit",
                "git.tag",
                "git.distance",
                "git.dirty",
                "git.shallow",
            ):
                availability = (
                    "Requires a Git version source."
                    if field.startswith("git.")
                    else "Requires a supported SemVer value."
                    if field
                    in {
                        "major",
                        "minor",
                        "patch",
                        "prerelease",
                        "build_metadata",
                        "sort_key",
                    }
                    else "Requires this repository's version to be resolved."
                )
                add(
                    f"{prefix}.{field}",
                    "Versions",
                    "Resolved version metadata.",
                    availability=availability,
                )
    for name, credential in mapping(value.get("credentials")).items():
        fields = mapping(credential).get("fields", ["token"])
        for field in fields if isinstance(fields, list) else []:
            add(
                f"secret:{name}.{field}",
                "Credentials",
                "Credential reference; never previewed.",
                ["secret"],
            )
    for field in sorted(GITHUB_FIELDS):
        add(
            f"github.{field}",
            "GitHub",
            "GitHub Actions event metadata.",
            ["destination"],
            availability="Available only in the corresponding GitHub event.",
        )
    return {"version": 1, "entries": list(entries.values())}
