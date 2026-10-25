"""Who is running ptk: maintainer or user (use case).

``maintainers.ptk.yml`` lists maintainers by git e-mail and/or OS user name;
``PTK_ROLE=maintainer|user`` forces a role. This only controls what is shown
(``--help``, the HTML help, VS Code tasks) - it is not access control.
"""

from __future__ import annotations

from typing import Literal

from ..ports import HostEnvironment
from .project import Project

Role = Literal["maintainer", "user"]


def resolve_role(project: Project | None, host: HostEnvironment) -> Role:
    forced = host.variables.get("PTK_ROLE", "").strip().lower()
    if forced in ("maintainer", "user"):
        return forced  # type: ignore[return-value]
    if project is None or project.maintainers is None:
        return "user"
    email, user = host.user_identity(project.root)
    for m in project.maintainers.maintainers:
        if m.email and email and m.email.lower() == email.lower():
            return "maintainer"
        if m.user and user and m.user.lower() == user.lower():
            return "maintainer"
    return "user"


def visible(audience: str, role: Role) -> bool:
    return audience == "all" or role == "maintainer"
