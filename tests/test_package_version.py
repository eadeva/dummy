"""Package metadata follows configured version discovery and immutable sdists."""

import subprocess

import pytest
import yaml

from ptk.domain.errors import ConfigError
from ptk.package_version import package_version
from tests.project_files import write_project


def configured_project(root, versioning):
    write_project(
        root / ".main.ptk.yml",
        yaml.safe_dump(
            {
                "repository": {"alias": "ptk", "config_path": "config"},
                "project": {"name": "ptk"},
                "variants": {"default": "release", "variants": {"release": {}}},
            }
        ),
    )
    (root / "config/versioning.ptk.yml").write_text(yaml.safe_dump(versioning))


def test_package_version_uses_versioning_file_and_default_variant(tmp_path):
    configured_project(
        tmp_path,
        {
            "project": {"source": "literal", "version": "1.2.3"},
            "variants": {
                "release": {"project": {"source": "literal", "version": "2.3.4-rc.1"}}
            },
        },
    )
    assert package_version(tmp_path) == "2.3.4rc1"
    assert package_version(tmp_path, resolved_version="7.8.9+2.gabc") == "7.8.9+2.gabc"


@pytest.mark.parametrize(
    "filename,contents",
    [
        ("artifactory_structure.ptk.yml", "artifactory: {}"),
        ("artifactory_paths.ptk.yml", "events: ["),
        ("jobs/broken.ptk.yml", "steps: ["),
        ("project.ptk.yml", "not_a_project: true"),
    ],
)
def test_package_version_does_not_load_unrelated_configuration(
    tmp_path, load, filename, contents
):
    configured_project(tmp_path, {"project": {"source": "literal", "version": "1.2.3"}})
    file = tmp_path / "config" / filename
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(contents)
    assert package_version(tmp_path) == "1.2.3"
    # Installing PTK must remain possible so users can diagnose/repair the project.
    # Ordinary project loading still rejects the same invalid document.
    with pytest.raises(ConfigError):
        load(tmp_path)


@pytest.mark.parametrize(
    "filename,contents",
    [
        (".main.ptk.yml", "repository: {alias: ptk, config_path: ../outside}"),
        ("config/project.variants.ptk.yml", "default: [release]"),
        ("config/versioning.ptk.yml", "project: {source: literal}"),
        (
            "config/versioning.ptk.yml",
            "project: {source: literal, version: 1.2.3, typo: 1}",
        ),
        ("config/versioning.ptk.yml", "project: ["),
    ],
)
def test_package_version_validates_its_inputs(tmp_path, filename, contents):
    configured_project(tmp_path, {"project": {"source": "literal", "version": "1.2.3"}})
    (tmp_path / filename).write_text(contents)
    with pytest.raises(ConfigError) as error:
        package_version(tmp_path)
    assert filename in str(error.value)


def test_package_version_without_variant_settings(tmp_path):
    configured_project(tmp_path, {"project": {"source": "literal", "version": "1.2.3"}})
    (tmp_path / "config/project.variants.ptk.yml").unlink()
    assert package_version(tmp_path) == "1.2.3"


def test_package_version_requires_versioning_document(tmp_path):
    configured_project(tmp_path, {})
    (tmp_path / "config/versioning.ptk.yml").unlink()
    with pytest.raises(ConfigError, match="versioning.ptk.yml"):
        package_version(tmp_path)


@pytest.mark.parametrize("filename", ["versioning.ptk.yml", "project.variants.ptk.yml"])
def test_package_version_rejects_symlink_inputs(tmp_path, filename):
    configured_project(tmp_path, {"project": {"source": "literal", "version": "1.2.3"}})
    file = tmp_path / "config" / filename
    target = tmp_path / "other.txt"
    file.replace(target)
    try:
        file.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ConfigError, match="symbolic links"):
        package_version(tmp_path)


def test_package_version_tracks_git_and_configured_fallback(tmp_path):
    configured_project(
        tmp_path,
        {
            "project": {
                "source": "git",
                "match": "release-*",
                "strip_prefix": "release-",
                "fallback": {"source": "literal", "version": "0.2.0.dev0"},
            }
        },
    )

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "PTK Test")
    git("config", "user.email", "test@example.invalid")
    git("add", ".")
    git("commit", "-qm", "initial")
    assert package_version(tmp_path) == "0.2.0.dev0"
    git("tag", "release-3.4.5")
    assert package_version(tmp_path) == "3.4.5"
    (tmp_path / "tracked").write_text("next")
    git("add", "tracked")
    git("commit", "-qm", "next")
    assert package_version(tmp_path).startswith("3.4.5+1.g")
    (tmp_path / "tracked").write_text("dirty")
    assert package_version(tmp_path).endswith(".dirty")


def test_sdist_version_wins_over_environment_and_unavailable_configuration(tmp_path):
    (tmp_path / "PKG-INFO").write_text("Name: ptk\nVersion: 4.5.6+2.gabc\n")
    assert package_version(tmp_path, resolved_version="9.9.9") == "4.5.6+2.gabc"


def test_invalid_package_version_fails_clearly(tmp_path):
    with pytest.raises(ValueError, match="not a valid Python package version"):
        package_version(tmp_path, resolved_version="release banana")
    (tmp_path / "PKG-INFO").write_text("Name: unrelated\nVersion: 1.0\n")
    with pytest.raises(ValueError, match="invalid PTK source distribution metadata"):
        package_version(tmp_path)
