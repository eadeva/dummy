"""Read the small, non-secret GitHub context used by destination templates."""

import json
from pathlib import Path

from ..domain.errors import PtkError


def github_context(environ):
    context = {
        name: environ["GITHUB_" + name.upper()]
        for name in (
            "event_name",
            "ref_name",
            "ref_type",
            "sha",
            "run_id",
            "run_attempt",
            "repository",
        )
        if "GITHUB_" + name.upper() in environ
    }
    context.setdefault("run_attempt", "1")
    event = {}
    if filename := environ.get("GITHUB_EVENT_PATH"):
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("event payload must be an object")
            for section, keys in (
                ("pull_request", ("number",)),
                ("release", ("tag_name", "prerelease")),
            ):
                body = payload.get(section, {})
                if not isinstance(body, dict):
                    raise TypeError(f"event {section} must be an object")
                event[section] = {key: body[key] for key in keys if key in body}
        except (OSError, ValueError, TypeError) as exc:
            raise PtkError(f"cannot read GitHub event metadata: {exc}") from None
    context["event"] = event
    return context
