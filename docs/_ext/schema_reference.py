"""Render configuration tables from the actual Pydantic JSON Schema."""

import inspect
import json
from collections import deque
from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive

from ptk.application.use_cases.project import ExportSchema
from ptk.domain.config.model import MaintainersSpec, PtkConfig


def fields(schema):
    """Use the same field order as configuration editors."""
    properties = schema.get("properties", {})
    order = schema.get("x-ptk-field-order", [])
    return [
        (key, properties[key])
        for key in dict.fromkeys([*order, *properties])
        if key in properties
    ]


def sections(schema, root):
    """Index reachable objects by configuration path, including recursive steps."""
    definitions = schema.get("$defs", {})
    paths = {}
    pending = deque([(root, schema)])
    result = []

    def visit(value, path, seen=frozenset()):
        if "$ref" in value:
            name = value["$ref"].rsplit("/", 1)[-1]
            if name in seen:
                return
            definition = definitions[name]
            if "properties" in definition:
                if name not in paths:
                    paths[name] = path
                    pending.append((path, definition))
            else:
                visit(definition, path, seen | {name})
        for alternative in value.get("anyOf", value.get("oneOf", [])):
            visit(alternative, path, seen)
        if "items" in value:
            visit(value["items"], path + "[]", seen)
        if isinstance(value.get("additionalProperties"), dict):
            visit(value["additionalProperties"], path + ".<name>", seen)

    while pending:
        path, definition = pending.popleft()
        result.append((path, definition))
        # Document shared tool shapes at their declarations, not usage sites.
        properties = sorted(
            fields(definition), key=lambda item: item[0] == "requires_tools"
        )
        for key, prop in properties:
            visit(prop, f"{path}.{key}" if path != root else key)
    return result, paths


def anchor(path):
    return "configuration-" + nodes.make_id(path)


def describe(schema, definitions, paths, *, grouped=False):
    """Render YAML value shapes and links, never Python model names."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in paths:
            path = paths[name]
            return [nodes.reference("", path, refid=anchor(path))]
        return describe(definitions[name], definitions, paths, grouped=grouped)
    alternatives = schema.get("anyOf", schema.get("oneOf"))
    if alternatives:
        result = []
        for item in alternatives:
            if result:
                result.append(nodes.Text(" | "))
            result.extend(describe(item, definitions, paths))
        return [nodes.Text("("), *result, nodes.Text(")")] if grouped else result
    if "enum" in schema:
        return [nodes.Text("one of " + json.dumps(schema["enum"]))]
    if "const" in schema:
        return [nodes.Text(json.dumps(schema["const"]))]
    kind = schema.get("type", "any")
    if kind == "array":
        return [
            nodes.Text("list of "),
            *describe(schema.get("items", {}), definitions, paths, grouped=True),
        ]
    if kind == "object" and isinstance(schema.get("additionalProperties"), dict):
        return [
            nodes.Text("mapping of names to "),
            *describe(schema["additionalProperties"], definitions, paths, grouped=True),
        ]
    return [nodes.Text(kind)]


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
        for model, root, title in (
            (PtkConfig, "configuration", "Assembled configuration"),
            (MaintainersSpec, "maintainers", "maintainers.ptk.yml"),
        ):
            schema = (
                ExportSchema().execute()
                if model is PtkConfig
                else model.model_json_schema(by_alias=True)
            )
            entries, paths = sections(schema, root)
            for path, definition in entries:
                section = nodes.section(
                    ids=[anchor(path)], classes=["ptk-configuration-section"]
                )
                section += nodes.title(text=title if path == root else path)
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
                for key, prop in fields(definition):
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
                        [nodes.literal(text=key)],
                        describe(prop, schema.get("$defs", {}), paths),
                        [
                            nodes.Text(
                                "yes" if key in definition.get("required", []) else "no"
                            )
                        ],
                        [nodes.Text(json.dumps(details) if details else "—")],
                        [nodes.Text(prop.get("description", "—"))],
                    )
                    row = nodes.row()
                    for value in values:
                        entry = nodes.entry()
                        entry += nodes.paragraph("", "", *value)
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
        "version": "3",
        "env_version": 3,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
