import json

import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli


def setup(tmp_path):
    file = tmp_path / "main.ptk.yml"
    file.write_text(
        yaml.safe_dump(
            {
                "project": {"name": "matrix", "default_action": "go"},
                "variants": {
                    "default": "small",
                    "components": {
                        "core": {
                            "features": {"SIZE": {"type": "int", "min": 1, "max": 9}}
                        }
                    },
                    "variants": {
                        "base": {"abstract": True},
                        "small": {"extends": "base"},
                        "large": {"extends": "base", "features": {"SIZE": 8}},
                    },
                },
                "actions": {
                    "go": {
                        "params": {"who": {"default": "world"}},
                        "steps": [
                            {
                                "show": {
                                    "uses": "echo",
                                    "with": {
                                        "message": "${vh.features.SIZE} ${params.who}"
                                    },
                                }
                            }
                        ],
                    }
                },
            }
        )
    )
    return file


def test_variant_edit_preview_and_persistence(tmp_path):
    file = setup(tmp_path)
    runner = CliRunner()
    prefix = ["-c", str(file), "variant"]
    preview = runner.invoke(
        cli,
        [
            *prefix,
            "new",
            "medium",
            "--extends",
            "small",
            "--feature",
            "SIZE=4",
            "--dry-run",
        ],
    )
    assert preview.exit_code == 0, preview.output
    assert not (tmp_path / "local.ptk.yml").exists()
    created = runner.invoke(
        cli, [*prefix, "new", "medium", "--extends", "small", "--feature", "SIZE=4"]
    )
    assert created.exit_code == 0, created.output
    selected = runner.invoke(cli, [*prefix, "set", "medium", "SIZE=5"])
    assert selected.exit_code == 0, selected.output
    result = runner.invoke(cli, ["-c", str(file), "go"])
    assert result.exit_code == 0, result.output
    assert "5 world" in result.output
    duplicate = runner.invoke(cli, [*prefix, "new", "medium"])
    assert duplicate.exit_code == 2


def test_all_variants_and_override_aliases(tmp_path):
    file = setup(tmp_path)
    result = CliRunner().invoke(
        cli,
        ["-c", str(file), "go", "--all-variants", "-bo", "SIZE=3", "-mp", "who=team"],
    )
    assert result.exit_code == 0, result.output
    summaries = [
        json.loads(p.read_text()) for p in (tmp_path / "_logs").rglob("run.json")
    ]
    assert {s["variant"] for s in summaries} == {"small", "large"}
    assert all(s["params"]["who"] == "team" for s in summaries)
    assert result.output.count("3 team") == 2


def test_variant_selection_preflight_and_dry_run(tmp_path):
    file = setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["-c", str(file), "go", "-V", "small,missing"])
    assert result.exit_code == 2
    assert not (tmp_path / "_logs").exists()
    preview = runner.invoke(
        cli, ["-c", str(file), "dry-run", "go", "-V", "small,large"]
    )
    assert preview.exit_code == 0, preview.output
    assert not (tmp_path / "_logs").exists()
