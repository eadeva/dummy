"""Render configuration tables from the actual Pydantic JSON Schema."""

import inspect
import json
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive

from ptk.application.use_cases.project import ExportSchema
from ptk.domain.config.model import MaintainersSpec, PtkConfig


def describe(schema):
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " | ".join(describe(item) for item in schema["anyOf"])
    if "enum" in schema:
        return "one of " + json.dumps(schema["enum"])
    if "const" in schema:
        return json.dumps(schema["const"])
    kind = schema.get("type", "any")
    if kind == "array":
        return "list of " + describe(schema.get("items", {}))
    if kind == "object" and isinstance(schema.get("additionalProperties"), dict):
        return "mapping to " + describe(schema["additionalProperties"])
    return kind


class SchemaReference(Directive):
    has_content = False

    def run(self):
        # Rebuild tables when schema code changes, including incremental builds.
        domain = Path(inspect.getfile(PtkConfig)).resolve().parents[1]
        for source in [
            Path(__file__),
            Path(inspect.getfile(ExportSchema)),
            *domain.rglob("*.py"),
        ]:
            self.state.document.settings.env.note_dependency(str(source.resolve()))
        result = []
        for model in (PtkConfig, MaintainersSpec):
            schema = (
                ExportSchema().execute()
                if model is PtkConfig
                else model.model_json_schema(by_alias=True)
            )
            models = {model.__name__: schema, **schema.get("$defs", {})}
            for name, definition in models.items():
                if "properties" not in definition:
                    continue
                section = nodes.section(ids=[f"schema-{name.lower()}"])
                section += nodes.title(text=name)
                table = nodes.table(classes=["tight-table"])
                group = nodes.tgroup(cols=5)
                for width in (18, 22, 8, 22, 30):
                    group += nodes.colspec(colwidth=width)
                head = nodes.thead()
                row = nodes.row()
                for label in (
                    "Field",
                    "Type",
                    "Required",
                    "Default / constraints",
                    "Description",
                ):
                    entry = nodes.entry()
                    entry += nodes.paragraph(text=label)
                    row += entry
                head += row
                group += head
                body = nodes.tbody()
                for key, prop in definition["properties"].items():
                    details = {
                        k: v
                        for k, v in prop.items()
                        if k
                        in {
                            "default",
                            "minimum",
                            "maximum",
                            "exclusiveMinimum",
                            "exclusiveMaximum",
                            "minItems",
                            "maxItems",
                            "pattern",
                        }
                    }
                    values = (
                        key,
                        describe(prop),
                        "yes" if key in definition.get("required", []) else "no",
                        json.dumps(details) if details else "—",
                        prop.get("description", "—"),
                    )
                    row = nodes.row()
                    for value in values:
                        entry = nodes.entry()
                        entry += nodes.paragraph(text=value)
                        row += entry
                    body += row
                group += body
                table += group
                section += table
                result.append(section)
        return result


def setup(app):
    app.add_directive("ptk-schema", SchemaReference)
    return {
        "version": "2",
        "env_version": 2,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
