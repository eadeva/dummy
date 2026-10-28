"""Generate/check the VS Code form schema from PTK's authored-YAML exporter."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import warnings
from pathlib import Path

from pydantic.json_schema import (
    GenerateJsonSchema,
    JsonSchemaValue,
    PydanticJsonSchemaWarning,
)
from pydantic_core import core_schema

from ptk.application.use_cases.project import ExportSchema

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "extensions/project-toolkit/media/config-schema.json"
REGENERATE = "uv run python scripts/generate_config_schema.py"


class EditorSchemaGenerator(GenerateJsonSchema):
    """Include model-owned factory defaults when a user adds a form field.

    Pydantic normally omits these defaults. PTK factories must be pure,
    deterministic and independent of input data to have a static form default.
    Use Pydantic's encoder so nested models and aliases retain JSON types.
    """

    def default_schema(self, schema: core_schema.WithDefaultSchema) -> JsonSchemaValue:
        if factory := schema.get("default_factory"):
            if schema.get("default_factory_takes_data"):
                raise ValueError("Form defaults cannot depend on validated input data")
            schema = {**schema, "default": factory()}
            schema.pop("default_factory")
        return super().default_schema(schema)


def generate_schema() -> dict:
    # Retain the CLI's authored step/workflow forms, includes, aliases, shorthand
    # unions and workspace rules. Do not duplicate those adaptations here.
    with warnings.catch_warnings():
        warnings.simplefilter("error", PydanticJsonSchemaWarning)
        return ExportSchema().execute(schema_generator=EditorSchemaGenerator)


def render(schema: dict, *, canonical: bool = False) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=canonical) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail on drift; never write"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    expected = generate_schema()
    if render(expected, canonical=True) != render(generate_schema(), canonical=True):
        parser.error("Model defaults produced a non-deterministic schema")
    if args.check:
        try:
            actual = json.loads(args.output.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(
                f"Cannot read schema: {exc}\nRegenerate: {REGENERATE}", file=sys.stderr
            )
            return 1
        before, after = render(actual, canonical=True), render(expected, canonical=True)
        if before != after:
            print(
                f"Config schema is out of date. Regenerate: {REGENERATE}",
                file=sys.stderr,
            )
            sys.stderr.writelines(
                difflib.unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile=str(args.output),
                    tofile="generated from PTK models",
                )
            )
            return 1
        print("Config schema matches PTK models.")
        return 0
    args.output.write_text(render(expected), encoding="utf-8", newline="\n")
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
