"""Destination-only Artifactory rules and pure path composition."""

from fnmatch import fnmatchcase
from urllib.parse import quote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config.dates import valid_date_field
from .config.substitution import iter_references, split_reference
from .config.template_variables import GIT_FIELDS, GITHUB_FIELDS


class PathRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match: str | None = Field(
        default=None,
        description="Branch glob (fnmatch, e.g. release/*) selecting this route in a branch route list; omit for the fallback route.",
    )
    path: str = Field(
        description="Relative destination path for this route. Supports PTk variables."
    )
    repository: str | None = Field(
        default=None, description="Override the Artifactory repository for this route."
    )
    name: str | None = Field(
        default=None, description="Override the file name template for this route."
    )


class EventRoute(BaseModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"default": {"path": ""}}
    )
    path: str | None = Field(
        default=None,
        description="Relative path for this event. Choose a single path or separate branch/tag routes.",
    )
    repository: str | None = Field(
        default=None, description="Override the Artifactory repository for this event."
    )
    name: str | None = Field(
        default=None, description="Override the file name template for this event."
    )
    branch: PathRoute | list[PathRoute] | None = Field(
        default=None,
        description="Destination for a push to a branch: one route, or a list whose first route with a matching branch glob (or without match) is used. Only valid for the push event.",
    )
    tag: PathRoute | None = Field(
        default=None,
        description="Destination for a push of a tag. Only valid for the push event.",
    )

    @model_validator(mode="after")
    def shape(self):
        if (self.path is not None) == (self.branch is not None or self.tag is not None):
            raise ValueError("choose an event path or branch/tag routes")
        single = [self.tag] + ([] if isinstance(self.branch, list) else [self.branch])
        if any(route is not None and route.match is not None for route in single):
            raise ValueError("match is only valid in a list of branch routes")
        return self


class JobDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(
        default="",
        description="Job-specific path appended after the base and event destination paths.",
    )


class ArtifactoryStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(
        description="HTTPS Artifactory base URL without credentials, query or fragment."
    )
    repository: str = Field(
        description="Default Artifactory repository for uploaded artifacts."
    )
    base_path: str = Field(
        default="",
        description="Relative path prefix shared by all artifact destinations.",
    )
    name: str | None = Field(
        default=None,
        description="File name template of generated-workflow uploads, for example ${run.job}_${run.variant}_${version.current.value}. Files are stored directly in the destination as NAME[_ARTIFACT_TYPE].zip with NAME.ptk-manifest.json; omit for opaque ptk/<hash> folders.",
    )
    events: dict[str, EventRoute] = Field(
        description="Destination routes keyed by event name, for example push or pull_request.",
        min_length=1,
    )
    jobs: dict[str, JobDestination] = Field(
        description="Optional destination suffixes keyed by job name.",
        default_factory=dict,
    )

    @model_validator(mode="after")
    def event_routes(self):
        for event, route in self.events.items():
            if event != "push" and (route.branch is not None or route.tag is not None):
                raise ValueError("branch/tag routes are only valid for the push event")
        return self


def template_problems(spec, variables):
    """Validate references without requiring a live GitHub runner or version lookup."""

    def walk(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from walk(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, (*path, index))
        elif isinstance(value, str):
            for ref in iter_references(value):
                ns, rest = split_reference(ref)
                valid = (
                    ns == "env"
                    or ns == "date"
                    and valid_date_field(rest)
                    or ns == "github"
                    and rest in GITHUB_FIELDS
                    or ns == "git"
                    and rest in GIT_FIELDS
                    or ns == "project"
                    and rest in {"alias", "name", "root", "description"}
                    or ns == "run"
                    and rest in {"job", "variant"}
                    or ns == "version"
                    and rest.startswith(("current.", "projects."))
                    or ns == "vars"
                    and rest.split(".")[0] in variables
                )
                if not valid:
                    yield path, f"unsupported destination reference {ref!r}"

    return list(walk(spec.model_dump(exclude_none=True)))


def relative_path(value):
    if not isinstance(value, str):
        raise TypeError("destination path must resolve to a string")
    if not value:
        return ""
    if (
        value.startswith("/")
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError(
            "destination paths must be relative paths without control characters"
        )
    value = value.rstrip("/")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("destination paths cannot contain empty, '.' or '..' segments")
    return value


def destination(spec, scope, *, event, ref_type, job, include_base=False):
    route = spec.events.get(event)
    if route is None:
        raise ValueError(f"no Artifactory destination configured for event {event!r}")
    selected = route
    if route.path is None:
        selected = (
            getattr(route, ref_type, None) if ref_type in {"branch", "tag"} else None
        )
        if isinstance(selected, list):
            branch = scope("${git.branch}")
            selected = next(
                (
                    r
                    for r in selected
                    if r.match is None or fnmatchcase(branch, r.match)
                ),
                None,
            )
        if selected is None:
            raise ValueError(
                f"no Artifactory destination configured for push ref type {ref_type!r}"
            )
    repository = scope(selected.repository or route.repository or spec.repository)
    if not isinstance(repository, str) or not repository or "/" in repository:
        raise ValueError("Artifactory repository must be one nonempty path segment")
    relative_path(repository)
    base_url = scope(spec.url)
    if not isinstance(base_url, str):
        raise TypeError("Artifactory URL must resolve to a string")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(ord(c) < 32 or ord(c) == 127 for c in base_url)
    ):
        raise ValueError(
            "Artifactory URL must be HTTPS without credentials, query or fragment"
        )
    suffix = spec.jobs[job].path if job in spec.jobs else ""
    parts = [
        relative_path(scope(value)) for value in (spec.base_path, selected.path, suffix)
    ]

    def compose(selected_parts):
        path = "/".join(part for part in selected_parts if part)
        encoded = "/".join(
            quote(part, safe="") for part in (repository, *path.split("/")) if part
        )
        return {
            "url": base_url.rstrip("/") + "/" + encoded + "/",
            "repository": repository,
            "path": path,
        }

    result = compose(parts)
    template = getattr(selected, "name", None) or route.name or spec.name
    if template:
        name = scope(template)
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValueError("Artifactory file name must resolve to one path segment")
        relative_path(name)
        result["name"] = name
    if include_base:
        result["base"] = compose(parts[:2])
    return result
