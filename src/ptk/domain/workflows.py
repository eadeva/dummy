"""Declarative job orchestration; workflow groups never merge repository settings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NAME = r"^[a-z][a-z0-9-]*$"


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(
        description="Unique name of this workflow entry, written as the YAML mapping key.",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    job: str | None = Field(
        description="Job to call. Choose either a job call or a group of child steps.",
        default=None,
        pattern=NAME,
    )
    repo: str | None = Field(
        description="Repository alias owning the job. Omit for the workflow’s own repository.",
        default=None,
        pattern=NAME,
    )
    params: dict[str, Any] = Field(
        description="Parameter values supplied to the called job.", default_factory=dict
    )
    steps: list[WorkflowNode] | None = Field(
        description="Nested workflow entries in this group.", default=None, min_length=1
    )
    parallel: bool = Field(
        default=False,
        description="Run the child entries concurrently. Only valid for groups.",
    )
    continue_on_error: bool = Field(
        default=False, description="Continue the workflow after this entry fails."
    )

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, value):
        return entries(value) if value is not None else None

    @model_validator(mode="after")
    def _shape(self):
        if (self.job is None) == (self.steps is None):
            raise ValueError("choose exactly one of job or steps")
        if self.job is not None and self.parallel:
            raise ValueError("parallel belongs on a group with steps")
        if self.steps is not None and (self.repo or self.params):
            raise ValueError("repo and params belong on job calls")
        return self


def entries(value):
    if not isinstance(value, list):
        raise ValueError("workflow steps must be a list of named entries")  # noqa: TRY004 - Pydantic validation
    result = []
    names = set()
    for entry in value:
        if isinstance(entry, WorkflowNode):
            name, body = entry.name, entry
        elif isinstance(entry, dict) and len(entry) == 1:
            name, body = next(iter(entry.items()))
            if isinstance(body, str):
                body = {"job": body}
            if not isinstance(body, dict):
                raise ValueError("workflow entries need a job or a group")  # noqa: TRY004 - Pydantic validation
            body = {**body, "name": name}
        elif isinstance(entry, dict) and "name" in entry:
            name, body = entry["name"], entry
        else:
            raise ValueError("workflow steps must have one name each")
        if not isinstance(name, str):
            raise ValueError("workflow step names must be strings")  # noqa: TRY004 - Pydantic validation
        if name in names:
            raise ValueError(f"duplicate workflow step name {name!r}")
        names.add(name)
        result.append(body)
    return result


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
        description="Open the aggregate report after every run (always), only on failures (on-errors), or disable automatic opening (null).",
    )
    parallel: bool = Field(
        default=False, description="Run top-level workflow entries concurrently."
    )
    max_workers: int = Field(
        description="Maximum number of concurrent workflow workers.",
        default=4,
        ge=1,
        le=32,
    )
    steps: list[WorkflowNode] = Field(
        description="Ordered job calls or nested groups. At least one entry is required.",
        min_length=1,
    )

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, value):
        return entries(value)


class WorkflowFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflows: dict[str, WorkflowSpec] = Field(
        description="Named workflows defined in this document.", default_factory=dict
    )

    @field_validator("workflows")
    @classmethod
    def _names(cls, value):
        import re

        for name in value:
            if not re.fullmatch(NAME, name):
                raise ValueError(f"invalid workflow name {name!r}")
        return value
