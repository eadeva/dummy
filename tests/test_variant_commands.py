import json

import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.project_files import read_project, write_project


def setup(tmp_path):
    file = tmp_path / ".main.ptk.yml"
    write_project(
        file,
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "matrix", "default_job": "go"},
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
                "jobs": {
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
        ),
    )
    return file


def test_all_variants_and_override_aliases(tmp_path):
    file = setup(tmp_path)
    result = CliRunner().invoke(
        cli,
        ["-C", str(file), "go", "--all-variants", "-bo", "SIZE=3", "-mp", "who=team"],
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
    result = runner.invoke(cli, ["-C", str(file), "-V", "small,missing", "go"])
    assert result.exit_code == 2
    assert not (tmp_path / "_logs").exists()
    preview = runner.invoke(
        cli, ["-C", str(file), "-V", "small,large", "dry-run", "go"]
    )
    assert preview.exit_code == 0, preview.output
    assert not (tmp_path / "_logs").exists()


def test_matrix_failure_preserves_later_runs(tmp_path):
    import sys

    file = setup(tmp_path)
    config = read_project(file)
    config["jobs"]["go"]["steps"].append(
        {
            "fail_small": {
                "run": [sys.executable, "-c", "raise SystemExit(3)"],
                "when": "variant == 'small'",
            }
        }
    )
    write_project(file, yaml.safe_dump(config))
    result = CliRunner().invoke(cli, ["-C", str(file), "go", "--all-variants"])
    assert result.exit_code == 1, result.output
    summaries = {
        json.loads(p.read_text())["variant"]: json.loads(p.read_text())["status"]
        for p in (tmp_path / "_logs").rglob("run.json")
    }
    assert summaries == {"large": "passed", "small": "failed"}


def test_global_feature_override(tmp_path):
    file = setup(tmp_path)
    result = CliRunner().invoke(cli, ["-C", str(file), "--set", "vh.SIZE=6", "go"])
    assert result.exit_code == 0, result.output
    assert "6 world" in result.output
