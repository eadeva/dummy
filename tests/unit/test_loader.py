from pathlib import Path

import pytest

from ptk.adapters.config.yaml_loader import YamlConfigReader
from ptk.domain.config import tree as t
from ptk.domain.errors import ConfigError


def read(root: Path, name: str = "main.ptk.yml"):
    reader = YamlConfigReader(display_root=root)
    return reader.read(root / name), reader


def test_include_order_and_main_file_wins(write):
    root = write(
        {
            "main.ptk.yml": """
            include: [parts/*.ptk.yml]
            vars: {a: main}
        """,
            "parts/1.ptk.yml": "vars: {a: one, b: one}",
            "parts/2.ptk.yml": "vars: {b: two, c: two}",
        }
    )
    node, reader = read(root)
    assert t.to_plain(node) == {"vars": {"a": "main", "b": "two", "c": "two"}}
    prov = t.provenance(node)
    assert str(prov[("vars", "b")]) == "parts/2.ptk.yml:1"
    assert len(reader.files) == 3


def test_include_tag_glob_merges_mappings_and_concatenates_lists(write):
    root = write(
        {
            "main.ptk.yml": """
            tools: !include tools/*.ptk.yml
            list: !include lists/*.ptk.yml
        """,
            "tools/a.ptk.yml": "cmake: {version: '>=3.28'}",
            "tools/b.ptk.yml": "ninja: {version: '>=1.11'}",
            "lists/a.ptk.yml": "[1, 2]",
            "lists/b.ptk.yml": "[3]",
        }
    )
    # lists as top-level documents are only allowed via !include, not as main file
    node, _ = read(root)
    data = t.to_plain(node)
    assert set(data["tools"]) == {"cmake", "ninja"}
    assert data["list"] == [1, 2, 3]


def test_replace_and_append_tags(write):
    root = write(
        {
            "main.ptk.yml": """
        include: [base.ptk.yml]
        environment:
          set: !replace {ONLY: "1"}
          keep: !append [B]
    """,
            "base.ptk.yml": """
        environment:
          set: {A: "1", B: "2"}
          keep: [A]
    """,
        }
    )
    data = t.to_plain(read(root)[0])
    assert data["environment"] == {"set": {"ONLY": "1"}, "keep": ["A", "B"]}


def test_variants_string_is_include_sugar(write):
    root = write(
        {
            "main.ptk.yml": "variants: product/line.ptk.yml",
            "product/line.ptk.yml": "default: a\nvariants: {a: {}}",
        }
    )
    assert t.to_plain(read(root)[0])["variants"]["default"] == "a"


@pytest.mark.parametrize(
    "files, message",
    [
        ({"main.ptk.yml": "a: 1\na: 2"}, "duplicate key 'a'"),
        (
            {
                "main.ptk.yml": "include: [x.ptk.yml]",
                "x.ptk.yml": "include: [main.ptk.yml]",
            },
            "include cycle",
        ),
        ({"main.ptk.yml": "include: [missing.ptk.yml]"}, "included file not found"),
        ({"main.ptk.yml": "a: !foo 1"}, "unknown tag !foo"),
        ({"main.ptk.yml": "a: [1"}, "invalid YAML"),
        ({"main.ptk.yml": "- 1"}, "top level must be a mapping"),
    ],
)
def test_errors_have_locations(write, files, message):
    root = write(files)
    with pytest.raises(ConfigError) as exc:
        read(root)
    assert message in str(exc.value)
    assert "ptk.yml" in str(exc.value)


def test_yaml_anchors_and_merge_keys(write):
    root = write(
        {
            "main.ptk.yml": """
        defaults: &d {timeout: 10, retries: 1}
        step: {<<: *d, retries: 3}
    """
        }
    )
    assert t.to_plain(read(root)[0])["step"] == {"timeout": 10, "retries": 3}


def test_locate_and_display_path_for_steps(write):
    root = write(
        {
            "main.ptk.yml": """
        actions:
          build:
            steps:
              - first: {run: a}
              - group:
                  steps:
                    - inner: {run: b}
    """
        }
    )
    node, _ = read(root)
    path = ("actions", "build", "steps", 1, "steps", 0, "run")
    assert t.locate(node, path).line == 7
    assert t.display_path(node, path) == "actions.build.steps.group.steps.inner.run"
