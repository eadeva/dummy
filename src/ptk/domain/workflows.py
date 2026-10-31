"""Named job invocations and their dependency graph."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .graphs import IDENTIFIER, DependencyId, ancestors, validate_graph

NAME = r"^[a-z][a-z0-9_-]*$"


class WorkflowJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job: str = Field(
        description="Job to invoke once in this workflow: JOB in the owner's repository or REPO:JOB. The same job name in another repository is distinct. Workspace-owned workflows require REPO:JOB.",
        pattern=r"^(?:[a-z][a-z0-9_-]*:)?[a-z][a-z0-9_-]*$",
    )
    needs: list[DependencyId] = Field(
        default_factory=list,
        description="Invocation IDs that must succeed before this job starts. Accepts one ID or a list. Omit for an immediately eligible job.",
    )
    params: dict[str, Any] = Field(
        description="Parameter values supplied to the called job.", default_factory=dict
    )
    continue_on_error: bool = Field(
        default=False,
        description="Allow dependents to run after this job fails and tolerate its failure in the workflow exit status. Reports retain the failure. Cancellation is never tolerated.",
    )

    @field_validator(
        "needs", mode="before", json_schema_input_type=DependencyId | list[DependencyId]
    )
    @classmethod
    def _needs(cls, value):
        return [value] if isinstance(value, str) else value

    @field_validator("needs")
    @classmethod
    def _unique(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("needs must not repeat an invocation ID")
        return value


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
        description="Named job invocations. IDs are local to this workflow and are referenced by needs. YAML order controls presentation only.",
        min_length=1,
        json_schema_extra={"propertyNames": {"pattern": IDENTIFIER}},
    )

    @model_validator(mode="after")
    def _graph(self):
        validate_graph(self.jobs, "workflow job")
        self.validate_job_targets()
        return self

    def validate_job_targets(self, owner: str | None = None):
        seen = {}
        for invocation, call in self.jobs.items():
            target = call.job if ":" in call.job else f"{owner or ''}:{call.job}"
            if target in seen:
                raise ValueError(
                    f"job {target.lstrip(':')!r} can only be chosen once per workflow; "
                    f"invocations {seen[target]!r} and {invocation!r} refer to it"
                )
            seen[target] = invocation

    def ancestors(self):
        return ancestors(self.jobs)


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
