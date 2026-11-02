import os

from ptk.adapters import output_cache
from tests.project_files import write_project
from tests.test_output_cache import consumer, producer, run

orig_fp = output_cache.LocalOutputCache.fingerprint
orig_read = output_cache.LocalOutputCache.read


def test_debug(tmp_path, monkeypatch, capsys):
    def fp(self, paths, cancel):
        value = orig_fp(self, paths, cancel)
        print("fingerprint", paths, os.getcwd(), value)
        if value is None:
            from pathlib import Path

            p = Path(paths[0])
            before = p.lstat()
            with p.open("rb") as f:
                s = os.fstat(f.fileno())
            after = p.lstat()
            print(
                "DIFF fstat",
                [
                    n
                    for n in dir(s)
                    if n.startswith("st_") and getattr(s, n) != getattr(before, n)
                ],
            )
            print(
                "DIFF after",
                [
                    n
                    for n in dir(s)
                    if n.startswith("st_") and getattr(after, n) != getattr(before, n)
                ],
            )
            print(before, s, sep="\n")
        return value

    def read(self, identity):
        value = orig_read(self, identity)
        print("read", identity, self.root, value)
        return value

    monkeypatch.setattr(output_cache.LocalOutputCache, "fingerprint", fp)
    monkeypatch.setattr(output_cache.LocalOutputCache, "read", read)
    (tmp_path / "source").write_text("one")
    write_project(
        tmp_path / ".main.ptk.yml",
        {
            "project": {"name": "reuse"},
            "jobs": {"go": {"steps": {"root": producer(), "child": consumer()}}},
        },
    )
    for _ in range(2):
        print("=== run")
        result, _ = run(tmp_path)
        print([(s.name, s.status, s.reused_from, s.message) for s in result.steps])
    with capsys.disabled():
        pass
    raise AssertionError("show output")
