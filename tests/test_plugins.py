import importlib
import textwrap
from types import SimpleNamespace

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.plugins import PluginInstaller, load_plugins
from ptk.domain.errors import PtkError
from ptk.domain.tools import InstallMethod
from ptk.drivers.cli.main import cli


def test_installed_plugin_distribution_end_to_end(tmp_path, monkeypatch):
    package = tmp_path / "plugin_site"
    package.mkdir()
    dist = package / "ptk_test_plugin-1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: ptk-test-plugin\nVersion: 1.0\n"
    )
    (dist / "entry_points.txt").write_text(
        textwrap.dedent("""
        [ptk.steps]
        custom.echo = ptk_test_extension:step
        [ptk.reporters]
        text = ptk_test_extension:report
        [ptk.report_contributors]
        custom = ptk_test_extension:contribute
        [ptk.secret_providers]
        custom = ptk_test_extension:Provider
        [ptk.generators]
        custom = ptk_test_extension:generate
        [ptk.installers]
        custom = ptk_test_extension:install
    """)
    )
    (package / "ptk_test_extension.py").write_text(
        textwrap.dedent("""
        events = []
        def step(step, out, ctx):
            events.append('step')
            out(step.env['TOKEN'])
            return 0
        def report(report, target):
            events.append('report')
            path = target / 'custom.txt'
            path.write_text(report.status)
            return path
        def contribute(folder, labels):
            events.append('contribute')
            return []
        def generate(variant):
            events.append('generate')
            return {'custom.txt': variant.name}
        def install(name, options, out):
            events.append('install')
            out(options['message'])
        class Provider:
            name = 'custom'
            can_store = False
            def available(self): return True, ''
            def get(self, key):
                events.append('secret')
                return 'plugin-secret'
            def store(self, key, value): raise ValueError('read only')
            def remove(self, key): return False
    """)
    )
    monkeypatch.syspath_prepend(str(package))
    root = tmp_path / "project"
    root.mkdir()
    config = root / ".main.ptk.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "plugins"},
                "plugins": ["ptk-test-plugin"],
                "reporting": {"formats": ["text"]},
                "variants": {"variants": {"one": {}}},
                "credentials": {"remote": {"providers": ["custom"]}},
                "jobs": {
                    "go": {
                        "steps": [
                            {
                                "custom": {
                                    "uses": "custom.echo",
                                    "env": {"TOKEN": "${secret:remote.token}"},
                                }
                            },
                            {
                                "gen": {
                                    "uses": "variant.generate",
                                    "with": {"generators": ["custom"]},
                                }
                            },
                        ]
                    }
                },
            }
        )
    )
    result = CliRunner().invoke(cli, ["-c", str(config), "go", "-V", "one"])
    assert result.exit_code == 0, result.output
    assert "plugin-secret" not in result.output
    module = importlib.import_module("ptk_test_extension")
    assert {"step", "secret", "report", "contribute", "generate"} <= set(module.events)
    assert (root / "_builds/one/go/gen/custom.txt").read_text() == "one"
    plugins = load_plugins(["ptk-test-plugin"])
    lines = []
    PluginInstaller(None, plugins["installers"]).install(
        "tool",
        InstallMethod("plugin:custom", "custom", options={"message": "installed"}),
        lines.append,
    )
    assert lines == ["installed"]
    assert load_plugins([])["steps"] == {}


def test_plugins_fail_on_missing_distribution_or_collision(monkeypatch):
    import ptk.adapters.plugins as adapter

    monkeypatch.setattr(adapter, "entry_points", lambda **kw: [])
    with pytest.raises(PtkError, match="no PTK entry points"):
        load_plugins(["missing"])
    entry = SimpleNamespace(
        name="echo",
        dist=SimpleNamespace(metadata={"Name": "bad"}),
        load=lambda: lambda: None,
    )
    monkeypatch.setattr(
        adapter,
        "entry_points",
        lambda **kw: [entry] if kw["group"] == "ptk.steps" else [],
    )
    with pytest.raises(PtkError, match="collision"):
        load_plugins(["bad"])
