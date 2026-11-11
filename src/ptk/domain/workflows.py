"""Named job invocations and their dependency graph."""

from __future__ import annotations

import re
from graphlib import CycleError, TopologicalSorter
from types import SimpleNamespace
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .graphs import ancestors, validate_graph

NAME = r"^[a-z][a-z0-9_-]*$"
TARGET = r"^(?:[a-z][a-z0-9_-]*:)?[a-z][a-z0-9_-]*$"
JobTarget = Annotated[str, StringConstraints(pattern=TARGET)]


def workflow_job_id(target: str) -> str:
    """Readable portable ID; WorkflowSpec rejects ambiguous target combinations."""
    repo, separator, job = target.partition(":")
    return f"repo_{repo}_job_{job}" if separator else f"job_{target}"


class WorkflowJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    needs: list[JobTarget] = Field(
        default_factory=list,
        description="Job keys that must succeed before this job starts. Accepts one ID or a list. Omit for an immediately eligible job.",
    )
    local_needs: list[JobTarget] = Field(
        default_factory=list,
        description="Job keys that must finish (with any result) before this job starts in a local run, e.g. because both use the same build folder. No outputs are exchanged; generated GitHub workflows ignore them.",
    )
    params: dict[str, Any] = Field(
        description="Parameter values supplied to the called job.", default_factory=dict
    )
    continue_on_error: bool = Field(
        default=False,
        description="Allow dependents to run after this job fails and tolerate its failure in the workflow exit status. Reports retain the failure. Cancellation is never tolerated.",
    )

    @field_validator(
        "needs",
        "local_needs",
        mode="before",
        json_schema_input_type=JobTarget | list[JobTarget],
    )
    @classmethod
    def _needs(cls, value):
        return [value] if isinstance(value, str) else value

    @field_validator("needs", "local_needs")
    @classmethod
    def _unique(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("needs must not repeat a job key")
        return value

    @model_validator(mode="after")
    def _disjoint(self):
        if both := set(self.needs) & set(self.local_needs):
            raise ValueError(
                f"{sorted(both)} listed in needs and local_needs; keep one"
            )
        return self


class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    help: str = Field(
        default="",
        description="Workflow description shown in command help and the extension.",
    )
    audience: Literal["all", "maintainer"] = Field(
        default="all",
        description="Choose whether everyone or only maintainers can access this workflow.",
    )
    open_report: Literal["always", "on-errors"] | None = Field(
        default="always",
        description="Open the full aggregate report on successful local runs with always. Active errors always open aggregate diagnostics locally, including with on-errors or null; CX never opens a browser.",
    )
    max_workers: int = Field(
        description="Maximum number of concurrent workflow jobs. Dependencies, not YAML order, determine when jobs become eligible.",
        default=4,
        ge=1,
        le=32,
    )
    jobs: dict[str, WorkflowJob] = Field(
        description="Jobs keyed directly by JOB or REPO:JOB. Values configure needs, params and error handling; no separate job field. Needs references these exact keys. YAML order controls presentation only.",
        min_length=1,
        json_schema_extra={"propertyNames": {"pattern": TARGET}},
    )

    @model_validator(mode="after")
    def _graph(self):
        validate_graph(self.jobs, "workflow job", identifier=TARGET)
        for name, job in self.jobs.items():
            for dependency in job.local_needs:
                if dependency == name or dependency not in self.jobs:
                    raise ValueError(
                        f"workflow job {name!r} local_needs unknown or own invocation {dependency!r}"
                    )
        try:
            tuple(
                TopologicalSorter(
                    {name: [*j.needs, *j.local_needs] for name, j in self.jobs.items()}
                ).static_order()
            )
        except CycleError as exc:
            raise ValueError(
                "workflow job dependency cycle (needs and local_needs): "
                + " -> ".join(exc.args[1])
            ) from None
        self.validate_job_targets()
        return self

    def validate_job_targets(self, owner: str | None = None):
        seen = {}
        ids = {}
        for invocation in self.jobs:
            identity = workflow_job_id(invocation)
            if identity in ids:
                raise ValueError(
                    f"workflow jobs {ids[identity]!r} and {invocation!r} produce "
                    f"the same generated ID {identity!r}; rename a repository alias "
                    "or job to make the IDs distinct"
                )
            ids[identity] = invocation
            target = invocation if ":" in invocation else f"{owner or ''}:{invocation}"
            if target in seen:
                raise ValueError(
                    f"job {target.lstrip(':')!r} can only be chosen once per workflow; "
                    f"invocations {seen[target]!r} and {invocation!r} refer to it"
                )
            seen[target] = invocation

    def ancestors(self):
        return ancestors(self.jobs)

    def local_ancestors(self):
        """Ordering of a local run: needs and local_needs together."""
        return ancestors(
            {
                name: SimpleNamespace(needs=[*job.needs, *job.local_needs])
                for name, job in self.jobs.items()
            }
        )


class WorkflowFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflows: dict[str, WorkflowSpec] = Field(
        description="Named workflows defined in this document.", default_factory=dict
    )

    @field_validator("workflows")
    @classmethod
    def _names(cls, value):
        for name in value:
            if not re.fullmatch(NAME, name):
                raise ValueError(f"invalid workflow name {name!r}")
        return value
