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
