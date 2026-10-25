import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli


def test_builtin_policy_applies_to_alias_help_and_execution(tmp_path, monkeypatch):
    config = tmp_path / "main.ptk.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "project": {"name": "access"},
                "command_audience": {"setup.creds": "maintainer"},
            }
        )
    )
    runner = CliRunner()
    monkeypatch.setenv("PTK_ROLE", "user")
    for path in (["setup", "creds", "list"], ["creds", "list"]):
        result = runner.invoke(cli, ["-c", str(config), *path])
        assert result.exit_code != 0
        assert "maintainer-only" in result.output
    help_result = runner.invoke(cli, ["-c", str(config), "setup", "--help"])
    assert "creds" not in help_result.output
    monkeypatch.setenv("PTK_ROLE", "maintainer")
    help_result = runner.invoke(cli, ["-c", str(config), "setup", "--help"])
    assert "creds" in help_result.output
    result = runner.invoke(cli, ["-c", str(config), "setup", "creds", "list"])
    assert result.exit_code == 0, result.output
