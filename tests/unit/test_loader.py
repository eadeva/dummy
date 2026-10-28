from pathlib import Path

import pytest
import yaml

from ptk.adapters.config import yaml_loader
from ptk.adapters.config.yaml_loader import YamlConfigReader
from ptk.domain.config import tree as t
from ptk.domain.errors import ConfigError


@pytest.fixture(autouse=True, params=["SafeLoader", "CSafeLoader"])
def parser_backend(request, monkeypatch):
    """YAML nodes, anchors and diagnostics must work with either backend."""
    parser = getattr(yaml, request.param, None)
    if parser is None:
        pytest.skip("PyYAML C extension unavailable")
    monkeypatch.setattr(yaml_loader, "_Loader", parser)


def read(root: Path, name: str = "fragment.ptk.yml"):
    reader = YamlConfigReader(display_root=root)
    return reader.read(root / name), reader


@pytest.mark.parametrize(
    "files, message",
    [
        ({"fragment.ptk.yml": "a: 1\na: 2"}, "duplicate key 'a'"),
        ({"fragment.ptk.yml": "a: !foo 1"}, "unknown tag !foo"),
        ({"fragment.ptk.yml": "a: [1"}, "invalid YAML"),
        ({"fragment.ptk.yml": "- 1"}, "top level must be a mapping"),
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
            "fragment.ptk.yml": """
        defaults: &d {timeout: 10, retries: 1}
        step: {<<: *d, retries: 3}
    """
        }
    )
    assert t.to_plain(read(root)[0])["step"] == {"timeout": 10, "retries": 3}


def test_locate_and_display_path_for_steps(write):
    root = write(
        {
            "fragment.ptk.yml": """
        jobs:
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
    path = ("jobs", "build", "steps", 1, "steps", 0, "run")
    assert t.locate(node, path).line == 7
    assert t.display_path(node, path) == "jobs.build.steps.group.steps.inner.run"
