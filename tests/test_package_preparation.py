"""Release output is owned, checked, and retained when a new build fails."""

import json

import pytest
from scripts import prepare_package


def previous_output(root):
    root.mkdir()
    wheel = root / "previous.whl"
    wheel.write_bytes(b"previous successful preparation")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "prepared_by": "ptk package",
                "files": {wheel.name: prepare_package.sha256(wheel)},
            }
        )
    )
    return wheel


def test_package_output_rejects_unowned_or_changed_files(tmp_path):
    output = tmp_path / "package"
    wheel = previous_output(output)
    prepare_package.owned_output(output)
    extra = output / "keep.txt"
    extra.write_text("user content")
    with pytest.raises(ValueError, match="changed or additional"):
        prepare_package.owned_output(output)
    assert wheel.read_bytes() == b"previous successful preparation"
    extra.unlink()
    wheel.write_bytes(b"modified")
    with pytest.raises(ValueError, match="changed or additional"):
        prepare_package.owned_output(output)


def test_failed_build_preserves_previous_package_output(tmp_path, monkeypatch):
    output = tmp_path / "package"
    previous_output(output)
    before = {path.name: path.read_bytes() for path in output.iterdir()}

    def fail(*args, **kwargs):
        raise ValueError("synthetic build failure")

    monkeypatch.setattr(prepare_package, "run", fail)
    with pytest.raises(ValueError, match="synthetic build failure"):
        prepare_package.prepare(output)
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}
    assert list(tmp_path.iterdir()) == [output]


def test_package_build_receives_the_resolved_run_version(tmp_path, monkeypatch):
    monkeypatch.setenv("PTK_VERSION_PTK", "7.8.9-rc.1+2.gabc")

    def check_build(*args, **kwargs):
        assert kwargs["env"]["_PTK_BUILD_VERSION"] == "7.8.9rc1+2.gabc"
        raise ValueError("checked snapshot")

    monkeypatch.setattr(prepare_package, "run", check_build)
    with pytest.raises(ValueError, match="checked snapshot"):
        prepare_package.prepare(tmp_path / "package")


def test_skill_link_check_accepts_aliased_project_root(tmp_path):
    project = tmp_path / "project"
    skill = project / ".github/skills/ptk-example/SKILL.md"
    doc = project / ".github/ptk/docs/guides/configuration.rst"
    skill.parent.mkdir(parents=True)
    doc.parent.mkdir(parents=True)
    doc.write_text("Configuration")
    skill.write_text("[Configuration](../../ptk/docs/guides/configuration.rst)")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(project, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable")
    prepare_package.check_skill_links(alias)


def test_skill_link_check_rejects_missing_and_external_targets(tmp_path):
    skill = tmp_path / ".github/skills/ptk-example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("[Missing](../../ptk/docs/missing.rst)")
    with pytest.raises(ValueError, match="broken installed skill reference"):
        prepare_package.check_skill_links(tmp_path)
    (tmp_path / "outside.rst").write_text("Outside the managed references")
    skill.write_text("[Outside](../../../outside.rst)")
    with pytest.raises(ValueError, match="broken installed skill reference"):
        prepare_package.check_skill_links(tmp_path)
