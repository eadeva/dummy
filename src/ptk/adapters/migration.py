"""File boundary for the one-off legacy converter."""

from pathlib import Path

import yaml

from ..domain.config.migration import migrate
from ..domain.errors import PtkError


def convert_file(source: Path, target: Path, *, name: str | None, dry_run: bool) -> str:
    try:
        if target.exists() or target.is_symlink():
            raise PtkError(f"refusing to overwrite {target}")
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
        text = yaml.safe_dump(
            migrate(data, name or source.parent.resolve().name),
            sort_keys=False,
            allow_unicode=True,
        )
        if not dry_run:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(text)
        return text
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PtkError(f"migration failed: {exc}") from None
