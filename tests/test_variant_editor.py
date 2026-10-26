import sys
from types import SimpleNamespace

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.variant_editor import launch_editor, save_edit
from ptk.application.use_cases.variant_editor import VariantEditorSession
from ptk.domain.config.model import PtkConfig
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli


@pytest.fixture
def session():
    return VariantEditorSession(
        PtkConfig.model_validate(
            {
                "project": {"name": "editor"},
                "variants": {
                    "components": {
                        "core": {
                            "features": {"SIZE": {"type": "int", "min": 1, "max": 5}}
                        }
                    },
                    "variants": {
                        "base": {"abstract": True},
                        "small": {"extends": "base"},
                    },
                    "default": "small",
                },
                "jobs": {"hello": {"steps": [{"say": {"uses": "echo"}}]}},
            }
        )
    )


def edited(session, value):
    data = yaml.safe_load(session.initial_text())
    data["variants"]["small"]["features"] = {"SIZE": value}
    return yaml.safe_dump(data)


def test_editor_validates_and_exports_standalone_project(session, tmp_path):
    target = tmp_path / "edited.ptk.yml"
    save_edit(session, edited(session, 3), target)
    result = CliRunner().invoke(cli, ["--config", str(target), "variant", "check"])
    assert result.exit_code == 0, result.output
    assert session.config.variants.variants["small"].features == {}
    data = yaml.safe_load(target.read_text())
    assert data["jobs"]["hello"]["steps"]
    assert data["variants"]["variants"]["small"]["features"]["SIZE"] == 3
    with pytest.raises(PtkError, match="cannot export"):
        save_edit(session, edited(session, 4), target)
    assert yaml.safe_load(target.read_text()) == data


def test_invalid_variant_cannot_be_saved(session, tmp_path):
    target = tmp_path / "bad.yml"
    with pytest.raises(PtkError, match="maximum"):
        save_edit(session, edited(session, 99), target)
    assert not target.exists()
    data = yaml.safe_load(session.initial_text())
    data["variants"]["base"]["extends"] = ["small"]
    with pytest.raises(PtkError):
        session.validate(yaml.safe_dump(data))


def test_plugin_is_loaded_only_when_selected(session, tmp_path, monkeypatch):
    import ptk.adapters.variant_editor as adapter

    calls = []
    plugin = SimpleNamespace(load=lambda: lambda s, p: calls.append((s, p)))
    monkeypatch.setattr(
        adapter, "entry_points", lambda **kw: [plugin] if kw["name"] == "test" else []
    )
    target = tmp_path / "export.yml"
    launch_editor(session, target, "test")
    assert calls == [(session, target)]
    with pytest.raises(PtkError, match="missing or ambiguous"):
        launch_editor(session, target, "unknown")


def test_desktop_error_is_actionable(session, tmp_path, monkeypatch):
    from ptk.drivers.gui.variants import open_editor

    class DisplayError(Exception):
        pass

    def unavailable():
        raise DisplayError("no display")

    monkeypatch.setitem(
        sys.modules,
        "tkinter",
        SimpleNamespace(
            Tk=unavailable,
            TclError=DisplayError,
            messagebox=None,
            scrolledtext=None,
            ttk=None,
        ),
    )
    with pytest.raises(PtkError, match="graphical desktop"):
        open_editor(session, tmp_path / "out.yml")


def test_editor_checks_job_references(session):
    session.config.jobs["hello"].steps[0].when = "SIZE > 0"
    data = yaml.safe_load(session.initial_text())
    data["components"]["core"]["features"] = {}
    with pytest.raises(PtkError, match="unknown name"):
        session.validate(yaml.safe_dump(data))
