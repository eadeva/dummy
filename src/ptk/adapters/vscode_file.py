"""Read and write ``.vscode/tasks.json`` (JSON with comments and trailing commas)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.errors import PtkError


def strip_jsonc(text: str) -> tuple[str, bool]:
    """JSONC -> JSON: drop // and /* */ comments outside strings and trailing commas.
    Returns the JSON text and whether comments were found."""
    out: list[str] = []
    i, n = 0, len(text)
    in_string = had_comments = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            out.append(ch)
        elif text.startswith("//", i):
            had_comments = True
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            had_comments = True
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    result = "".join(out)
    # drop trailing commas before } or ] (outside strings)
    cleaned: list[str] = []
    k, in_string = 0, False
    while k < len(result):
        ch = result[k]
        if in_string:
            cleaned.append(ch)
            if ch == "\\" and k + 1 < len(result):
                cleaned.append(result[k + 1])
                k += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            cleaned.append(ch)
        elif ch == "," and result[k + 1 :].lstrip()[:1] in ("}", "]"):
            pass
        else:
            cleaned.append(ch)
        k += 1
    return "".join(cleaned), had_comments


class TasksFile:
    def __init__(self, path: Path):
        self.path = path
        self.had_comments = False

    def read(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        text, self.had_comments = strip_jsonc(self.path.read_text(encoding="utf-8"))
        if not text.strip():
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PtkError(f"{self.path}: not valid JSON ({exc})") from None
        if not isinstance(data, dict):
            raise PtkError(f"{self.path}: expected a JSON object")
        return data

    def render(self, data: dict[str, Any]) -> str:
        return json.dumps(data, indent=4, ensure_ascii=False) + "\n"

    def write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.render(data), encoding="utf-8")
