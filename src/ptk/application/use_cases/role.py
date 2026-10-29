"""Who is running ptk: maintainer or user (use case).

``maintainers.ptk.yml`` lists login IDs. ``PTK_ROLE=user`` can reduce visibility;
environment variables cannot elevate a user to maintainer. This protects normal
CLI use, not against someone editing their own checkout or process environment.
"""

from __future__ import annotations

from typing import Literal

from ...domain.config.model import MaintainersSpec
from ..ports import HostEnvironment
from .project import Project

Role = Literal["maintainer", "user"]


def command_allowed(path: str, role: Role, policies: dict[str, str]) -> bool:
    if path == "maintainer" or path.startswith("maintainer."):
        return role == "maintainer"
    if role == "maintainer" or path in {
        "init",
        "validate",
        "self-service",
        "self-service.completion",
        "self-service.extension",
    }:
        return True
    parts = path.split(".")
    return all(
        policies.get(".".join(parts[:i])) != "maintainer"
        for i in range(1, len(parts) + 1)
    )


def resolve_role(project: Project | None, host: HostEnvironment) -> Role:
    return role_for_ids(project.maintainers if project else None, host)


def role_for_ids(maintainers: MaintainersSpec | None, host: HostEnvironment) -> Role:
    if (
        host.variables.get("PTK_ROLE", "").strip().lower() == "user"
        or maintainers is None
    ):
        return "user"
    user = host.user_id()
    return (
        "maintainer"
        if user and user.casefold() in {m.casefold() for m in maintainers.maintainers}
        else "user"
    )


def visible(audience: str, role: Role) -> bool:
    return audience == "all" or role == "maintainer"
