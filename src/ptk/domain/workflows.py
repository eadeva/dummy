"""Declarative action orchestration; workflow groups never merge repository settings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NAME = r"^[a-z][a-z0-9-]*$"


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    action: str | None = Field(default=None, pattern=NAME)
    repo: str | None = Field(default=None, pattern=NAME)
    variant: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowNode] | None = Field(default=None, min_length=1)
    parallel: bool = False
    continue_on_error: bool = False

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, value):
        return entries(value) if value is not None else None

    @model_validator(mode="after")
    def _shape(self):
        if (self.action is None) == (self.steps is None):
            raise ValueError("choose exactly one of action or steps")
        if self.action is not None and self.parallel:
            raise ValueError("parallel belongs on a group with steps")
        if self.steps is not None and (self.repo or self.variant or self.params):
            raise ValueError("repo, variant and params belong on action calls")
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
                body = {"action": body}
            if not isinstance(body, dict):
                raise ValueError("workflow entries need an action or a group")  # noqa: TRY004 - Pydantic validation
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
    help: str = ""
    audience: Literal["all", "maintainer"] = "all"
    open_report: Literal["always", "on-errors"] | None = "always"
    parallel: bool = False
    max_workers: int = Field(default=4, ge=1, le=32)
    steps: list[WorkflowNode] = Field(min_length=1)

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, value):
        return entries(value)


class WorkflowFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflows: dict[str, WorkflowSpec] = Field(default_factory=dict)

    @field_validator("workflows")
    @classmethod
    def _names(cls, value):
        import re

        for name in value:
            if not re.fullmatch(NAME, name):
                raise ValueError(f"invalid workflow name {name!r}")
        return value
