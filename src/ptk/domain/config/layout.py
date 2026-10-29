"""Conventional document ownership. Shared by loading, schemas and editor clients."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from pydantic import ConfigDict, create_model

from ..variants.model import ProductLineSpec
from . import tree as t
from .model import ProjectSpec, PtkConfig

MAIN_FIELDS = ("repository", "virtual_monorepo", "schema_version", "ptk_version")
PROJECT_FIELDS = (
    "vars",
    "param_defaults",
    "requires_tools",
    "environment",
    "logging",
    "reporting",
    "plugins",
    "command_audience",
)
SECTION_FILES = {
    "folder_structure.ptk.yml": "layout",
    "artifactory_paths.ptk.yml": "artifactory",
    "credentials.ptk.yml": "credentials",
    "tools.ptk.yml": "tools",
    "versioning.ptk.yml": "versioning",
    "configs.ptk.yml": "configs",
}
ENTITY_DIRECTORIES = {
    "jobs": ("jobs",),
    "workflows": ("workflows",),
    "variants": ("variants", "variants"),
}


def _fields(model, names):
    return {
        name: (model.model_fields[name].annotation, deepcopy(model.model_fields[name]))
        for name in names
    }


MainDocument = create_model(
    "MainDocument",
    __config__=ConfigDict(extra="forbid"),
    **_fields(PtkConfig, MAIN_FIELDS),
)
ProjectDocument = create_model(
    "ProjectDocument",
    __config__=ConfigDict(extra="forbid"),
    **_fields(ProjectSpec, ProjectSpec.model_fields),
    **_fields(PtkConfig, PROJECT_FIELDS),
)
VariantSettingsDocument = create_model(
    "VariantSettingsDocument",
    __config__=ConfigDict(extra="forbid"),
    **_fields(ProductLineSpec, ("default", "constraints", "env")),
)


@dataclass(frozen=True)
class Document:
    file: Path
    # A prefix mounts the entire document; fields mount individual root keys.
    prefix: tuple | None = None
    fields: dict | None = None

    def assemble(self, node):
        if self.prefix is not None:
            return t.overlay_for(self.prefix, node)
        result = t.Node({}, node.loc)
        for key, child in node.value.items():
            result = t.merge_unique(result, t.overlay_for(self.fields[key], child))
        return result

    def bindings(self):
        if self.prefix is not None:
            return [
                {"file": str(self.file), "path": list(self.prefix), "document_path": []}
            ]
        return [
            {"file": str(self.file), "path": list(path), "document_path": [key]}
            for key, path in self.fields.items()
        ]


def documents(main, config_path, components):
    root = main.parent / config_path
    result = [
        Document(main, fields={key: (key,) for key in MAIN_FIELDS}),
        Document(
            root / "project.ptk.yml",
            fields={
                **{key: ("project", key) for key in ProjectSpec.model_fields},
                **{key: (key,) for key in PROJECT_FIELDS},
            },
        ),
        Document(
            root / "project.variants.ptk.yml",
            fields={
                key: ("variants", key) for key in ("default", "constraints", "env")
            },
        ),
    ]
    result.extend(
        Document(root / name, prefix=(section,))
        for name, section in SECTION_FILES.items()
    )
    result.extend(
        Document(
            main.parent / spec["path"] / "component.variants.ptk.yml",
            prefix=("variants", "components", name),
        )
        for name, spec in components.items()
    )
    return result


def editor_layout(main, tree, schema):
    value = t.to_plain(tree) if tree else {}
    config_path = value.get("repository", {}).get("config_path", "config/ptk")
    components = value.get("project", {}).get("components", {})
    docs = documents(main, config_path, components)
    docs.extend(
        Document(
            main.parent / config_path / directory / "{name}.ptk.yml",
            prefix=(*prefix, "*"),
        )
        for directory, prefix in ENTITY_DIRECTORIES.items()
    )
    return {
        "bindings": [binding for doc in docs for binding in doc.bindings()],
        "documents": [
            {"file": str(doc.file), "schema": document_schema(schema, doc)}
            for doc in docs
        ],
    }


def schema_at(schema, path):
    node = schema
    for key in path:
        while "$ref" in node:
            node = schema["$defs"][node["$ref"].split("/")[-1]]
        if "anyOf" in node:
            node = next(part for part in node["anyOf"] if part.get("type") != "null")
            while "$ref" in node:
                node = schema["$defs"][node["$ref"].split("/")[-1]]
        node = node.get("properties", {}).get(key, node.get("additionalProperties", {}))
    return deepcopy(node)


def document_schema(schema, doc):
    if doc.prefix is not None:
        result = schema_at(schema, doc.prefix)
    else:
        properties = {key: schema_at(schema, path) for key, path in doc.fields.items()}
        result = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "x-ptk-field-order": list(properties),
        }
        if doc.file.name == "project.ptk.yml":
            result["required"] = ["name"]
        elif doc.file.name == ".main.ptk.yml":
            result["required"] = ["repository"]
            result["x-ptk-field-order"] = [
                key for key in schema["x-ptk-field-order"] if key in properties
            ]
    return result
