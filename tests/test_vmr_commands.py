"""ptk vmr: bundled git-repo launcher, manifest overrides and the reinit safety check."""

import subprocess
import xml.etree.ElementTree as ET

import pytest

from ptk.adapters import git_repo
from ptk.domain.errors import PtkError

LOCKED = """<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="origin" fetch="https://example.invalid/"/>
  <default remote="origin" revision="develop"/>
  <project name="kit" path="kit" revision="0e47db45eb2ba7a137a39ddb7f3afb898d3ec713" upstream="main" dest-branch="main"/>
  <project name="app" revision="1b508157e93e185a75a9e0133e93971948b3fc4a" upstream="develop" dest-branch="develop">
    <linkfile src="vnv" dest="app/docs/vnv"/>
  </project>
</manifest>
"""


def test_launcher_is_shipped_and_runs_with_ptk_python():
    launcher = git_repo.launcher()
    assert launcher.is_file()
    assert "Repo launcher" in launcher.read_text(encoding="utf-8")


def test_new_vmr_installs_git_repo_from_the_shipped_source(tmp_path, monkeypatch):
    shipped = tmp_path / "source"
    shipped.mkdir()
    (shipped / "main.py").write_text("# git-repo\n", encoding="utf-8")
    monkeypatch.setattr(git_repo, "source", lambda: shipped)
    environ = {"PTK_TOOLS_DIR": str(tmp_path / "tools")}
    repository = git_repo.local_repository(environ)
    assert repository == tmp_path / "tools" / "git-repo" / git_repo.VERSION
    assert (repository / "main.py").is_file()
    assert git_repo.git("rev-parse", "--abbrev-ref", "HEAD", cwd=repository) == "stable"
    assert git_repo.local_repository(environ) == repository
    assert not git_repo.git("status", "--porcelain", cwd=repository)


def test_source_checkout_lets_git_repo_download_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(git_repo, "source", lambda: None)
    assert git_repo.local_repository({"PTK_TOOLS_DIR": str(tmp_path)}) is None
    argv = git_repo.command(["init", "-u", "https://example.invalid/m.git"], tmp_path)
    assert "--repo-url" not in argv


def test_init_outside_a_vmr_points_git_repo_at_the_local_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(git_repo, "local_repository", lambda: tmp_path / "copy")
    argv = git_repo.command(["init", "-u", "https://example.invalid/m.git"], tmp_path)
    assert argv[argv.index("--repo-url") + 1] == str(tmp_path / "copy")
    assert "--no-repo-verify" in argv
    (tmp_path / ".repo" / "manifests.git").mkdir(parents=True)
    assert "--repo-url" not in git_repo.command(["init", "-b", "x"], tmp_path)


def test_revision_override_replaces_branch_and_keeps_other_projects():
    text = git_repo.override_revisions(LOCKED, {"app": "release/app/1.1.0"})
    projects = {p.get("name"): p for p in ET.fromstring(text).iter("project")}
    assert projects["app"].get("revision") == "release/app/1.1.0"
    assert projects["app"].get("upstream") is None
    assert projects["app"].find("linkfile").get("dest") == "app/docs/vnv"
    assert projects["kit"].get("revision").startswith("0e47db45")
    assert projects["kit"].get("upstream") == "main"
    # A commit keeps the recorded upstream branch; projects match by path too.
    text = git_repo.override_revisions(LOCKED, {"kit": "a" * 40})
    kit = next(p for p in ET.fromstring(text).iter("project") if p.get("name") == "kit")
    assert (kit.get("revision"), kit.get("upstream")) == ("a" * 40, "main")


def test_revision_override_rejects_unknown_projects():
    with pytest.raises(PtkError, match="unknown manifest project"):
        git_repo.override_revisions(LOCKED, {"missing": "develop"})


def test_manifest_reference_turns_files_into_urls(tmp_path):
    manifest = tmp_path / "vmr_manifest.xml"
    manifest.write_text(LOCKED)
    assert git_repo.manifest_reference(str(manifest)).startswith("file:///")
    assert git_repo.manifest_reference("https://example.invalid/m.xml") == (
        "https://example.invalid/m.xml"
    )
    with pytest.raises(PtkError, match="not found"):
        git_repo.manifest_reference(str(tmp_path / "missing.xml"))


def _workspace(tmp_path, standalone=None, origin=None):
    manifests = tmp_path / ".repo" / "manifests.git"
    manifests.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "--bare", str(manifests)], check=True)
    if origin:
        subprocess.run(
            ["git", "-C", str(manifests), "config", "remote.origin.url", origin],
            check=True,
        )
    if standalone:
        subprocess.run(
            ["git", "-C", str(manifests), "config", "manifest.standalone", standalone],
            check=True,
        )
    return tmp_path


def test_root_and_manifest_source(tmp_path):
    root = _workspace(tmp_path, origin="https://example.invalid/manifest.git")
    (root / "app" / "src").mkdir(parents=True)
    assert git_repo.find_root(root / "app" / "src") == root
    assert git_repo.manifest_source(root) == (
        "https://example.invalid/manifest.git",
        None,
    )
    with pytest.raises(PtkError, match="not inside a VMR"):
        git_repo.require_root(tmp_path.parent)


def test_standalone_manifest_uses_the_kept_repository_url(tmp_path):
    root = _workspace(tmp_path, standalone="file:///m.xml", origin="file:///m.xml")
    assert git_repo.manifest_source(root) == (None, "file:///m.xml")
    (root / ".repo" / git_repo.SAVED_URL).write_text("https://example.invalid/m.git\n")
    assert git_repo.manifest_source(root)[0] == "https://example.invalid/m.git"


def test_local_changes_lists_dirty_and_unpushed_projects(tmp_path, monkeypatch):
    def git(cwd, *args):
        subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)

    server = tmp_path / "server.git"
    git(tmp_path, "init", "-q", "--bare", str(server))
    root = tmp_path / "vmr"
    clean, dirty = root / "clean", root / "dirty"
    for path in (clean, dirty):
        git(tmp_path, "clone", "-q", str(server), str(path))
        git(path, "config", "user.name", "T")
        git(path, "config", "user.email", "t@example.invalid")
        (path / "f").write_text(path.name)
        git(path, "add", "f")
        git(path, "commit", "-qm", "one")
    git(clean, "push", "-q", "origin", "HEAD:main")
    git(dirty, "fetch", "-q")
    (dirty / "f").write_text("2")
    monkeypatch.setattr(git_repo, "projects", lambda _: [clean, dirty])
    problems = git_repo.local_changes(root)
    assert problems == [
        "dirty: uncommitted changes",
        "dirty: 1 commit(s) on local branches not pushed",
    ]


def test_vmr_commands_are_reserved_names():
    from ptk.domain.config.model import RESERVED_JOBS
    from ptk.drivers.cli.workspace_commands import RESERVED

    assert "vmr" in RESERVED_JOBS and "vmr" in RESERVED


def test_init_refuses_a_target_inside_a_vmr(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from ptk.drivers.cli.vmr import vmr_group

    root = _workspace(tmp_path / "vmr", origin="https://example.invalid/m.git")
    monkeypatch.chdir(root)
    result = CliRunner().invoke(vmr_group, ["init", "--dir", str(root / "sub")])
    assert result.exit_code != 0
    assert "inside the VMR" in result.output


def test_setup_job_uploads_the_vmr_manifest_when_enabled():
    from ptk.domain.workflows import WorkflowSpec
    from ptk.drivers.cli.github_workflows import CxSettings, render_workflow

    settings = CxSettings(
        runner_group="g",
        image="img",
        login="robot@example.invalid",
        token_secret="P_ROBOT_ARTIFACTORY_TOKEN",
        pmt_repository="XC-CE/pmt",
        pmt_version="v1",
        vmr=True,
        custom_checkout={"uses": "./checkout"},
        upload_manifest=True,
    )
    spec = WorkflowSpec.model_validate({"jobs": {"build": {}}})
    text = render_workflow(
        "rt1",
        spec,
        settings,
        job_files={"build": "call-build.yml"},
        env={},
        optional=set(),
    )
    assert "ptk vmr manifest -o" in text
    assert "maintainer cx upload-file" in text
    settings = CxSettings(**{**settings.__dict__, "upload_manifest": False})
    text = render_workflow(
        "rt1",
        spec,
        settings,
        job_files={"build": "call-build.yml"},
        env={},
        optional=set(),
    )
    assert "vmr manifest" not in text
