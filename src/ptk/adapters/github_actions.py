"""Runtime for the shipped composite Actions (PTK/Python and curl preinstalled)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote, urlsplit


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError(f"not a portable relative path: {value!r}")
    if value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError(f"not a portable relative path: {value!r}")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("control characters in path")
    return value


def local(root, value):
    target = root / relative(value)
    for part in [target, *target.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"symlink in output path: {value}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("output escapes repository")
    return target


def url(base, path):
    parsed = urlsplit(base)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(ord(c) < 33 for c in base)
    ):
        raise ValueError(
            "base-url must be an HTTPS URL without credentials/query/fragment"
        )
    return (
        base.rstrip("/")
        + "/"
        + "/".join(quote(p, safe="") for p in relative(path).split("/"))
    )


def identity(row):
    return {
        k: row.get(k) for k in ("repository", "job", "variant", "version", "commit")
    }


def location(row, scope):
    if not row.get("job") or not row.get("commit") or not scope:
        raise ValueError("producer identity requires job, commit and artifact-scope")
    key = hashlib.sha256(encode([scope, identity(row)]).encode()).hexdigest()
    return "ptk/" + key


class Curl:
    """Pass credentials through stdin, never command arguments or error output."""

    def __init__(self, user, token):
        if not user or not token or ":" in user:
            raise ValueError("technical-user and token are required")
        if any(c in user + token for c in "\r\n\x00"):
            raise ValueError("invalid credential characters")
        self.auth = (user + ":" + token).replace("\\", "\\\\").replace('"', '\\"')

    def transfer(self, address, path, *, upload=False, properties=None):
        if properties:
            for key, value in properties.items():
                if value is None:
                    continue
                values = value if isinstance(value, list) else [value]
                address += (
                    ";"
                    + quote(key, safe="")
                    + "="
                    + ",".join(quote(str(v), safe="") for v in values)
                )
        args = [
            "curl",
            "--disable",
            "--config",
            "-",
            "--silent",
            "--fail",
            "--proto",
            "=https",
            "--connect-timeout",
            "30",
            "--max-time",
            "3600",
            "--retry",
            "3",
            "--url",
            address,
        ]
        args += (
            ["--upload-file", str(path), "--output", os.devnull]
            if upload
            else ["--output", str(path)]
        )
        result = subprocess.run(
            args,
            check=False,
            input=f'user = "{self.auth}"\n',
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"curl {'upload' if upload else 'download'} failed (exit {result.returncode})"
            )


def properties_of(common, extra):
    if not isinstance(extra, dict) or any(
        not isinstance(k, str) or not k for k in extra
    ):
        raise ValueError("additional-properties must be a JSON object")
    if set(extra) & {
        "version",
        "commit",
        "variant_alias",
        "job",
        "step",
        "artifact_type",
        "repository",
    }:
        raise ValueError("additional-properties cannot replace producer identity")
    if any(
        not isinstance(v, (str, int, float, bool, list))
        or isinstance(v, list)
        and any(not isinstance(x, (str, int, float, bool)) for x in v)
        for v in extra.values()
    ):
        raise ValueError("property values must be scalars or scalar arrays")
    return {**common, **extra}


def pack(source, target):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(source.rglob("*")):
            if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
                raise ValueError(
                    f"directory output contains symlink/special file: {entry}"
                )
            archive.write(entry, entry.relative_to(source).as_posix())


def upload(manifest, root, base, row, scope, extra, transfer):
    if manifest.get("schema_version") != 1 or not isinstance(
        manifest.get("files"), list
    ):
        raise ValueError("unsupported upload manifest")
    row = row or manifest.get("producer", {})
    if manifest.get("repository") != row.get("repository"):
        raise ValueError("upload repository differs from setup matrix")
    if "producer" in manifest and identity(manifest["producer"]) != identity(row):
        raise ValueError("upload producer differs from setup matrix")
    prefix = location(row, scope)
    records = []
    with tempfile.TemporaryDirectory(prefix="ptk-upload-") as temporary:
        temp = Path(temporary)
        # Validate and package all declared outputs before the first transfer.
        pending = []
        for index, item in enumerate(manifest["files"]):
            rel = relative(item.get("relative_path"))
            source = local(root, rel)
            if Path(item["path"]).resolve() != source.resolve():
                raise ValueError(
                    "manifest path does not match repository-relative path"
                )
            props = item["properties"]
            if any(props.get(k) != row.get(k) for k in ("job", "version", "commit")):
                raise ValueError("upload identity differs from setup matrix")
            if (row.get("variant") or "default") not in props.get("variant_alias", []):
                raise ValueError("upload variant differs from setup matrix")
            kind = item["kind"]
            if (
                kind not in {"file", "directory"}
                or (kind == "file" and not source.is_file())
                or (kind == "directory" and not source.is_dir())
            ):
                raise ValueError(f"output kind changed: {rel}")
            payload = source
            if kind == "directory":
                payload = temp / f"{index}.zip"
                pack(source, payload)
            suffix = relative(item.get("upload_path") or rel) + (
                ".zip" if kind == "directory" else ""
            )
            remote = f"{prefix}/{manifest['run_id']}/{index}/{suffix}"
            relative(remote)
            record = {
                "relative_path": rel,
                "kind": kind,
                "remote_path": remote,
                "sha256": digest(payload),
                "mode": stat.S_IMODE(source.stat().st_mode),
                "properties": properties_of(props, extra),
            }
            records.append(record)
            pending.append((payload, record))
        for payload, record in pending:
            transfer.transfer(
                url(base, record["remote_path"]),
                payload,
                upload=True,
                properties=record["properties"],
            )
        document = {
            "schema_version": 1,
            "identity": identity(row),
            "scope": scope,
            "files": records,
        }
        published = temp / "manifest.json"
        published.write_text(encode(document), encoding="utf-8")
        # Publish last: consumers never see a partially uploaded set.
        transfer.transfer(url(base, prefix + "/manifest.json"), published, upload=True)
    return url(base, prefix + "/manifest.json")


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        seen = set()
        for member in bundle.infolist():
            name = relative(member.filename.rstrip("/"))
            if name in seen:
                raise ValueError("duplicate ZIP member")
            seen.add(name)
            mode = member.external_attr >> 16
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError("ZIP symlinks and special files are unsupported")
            local(destination, name)
        bundle.extractall(destination)
        for member in bundle.infolist():
            mode = member.external_attr >> 16
            if mode:
                (destination / member.filename).chmod(stat.S_IMODE(mode) & 0o777)


def download(producers, root, scope, transfer, base=""):
    restored, targets, pending = [], [], []
    with tempfile.TemporaryDirectory(prefix="ptk-download-") as temporary:
        temp = Path(temporary)
        for producer in producers:
            prefix = location(producer, scope)
            source_base = (producer.get("upload") or {}).get("url") or base
            path = temp / f"manifest-{len(pending)}.json"
            transfer.transfer(url(source_base, prefix + "/manifest.json"), path)
            document = json.loads(path.read_text(encoding="utf-8"))
            if (
                document.get("schema_version") != 1
                or document.get("identity") != identity(producer)
                or document.get("scope") != scope
            ):
                raise ValueError("download manifest identity mismatch")
            directory = producer.get("working_directory", ".")
            producer_root = root if directory == "." else local(root, directory)
            for record in document["files"]:
                target = local(producer_root, record["relative_path"])
                if any(
                    target == p or target.is_relative_to(p) or p.is_relative_to(target)
                    for p in targets
                ):
                    raise ValueError(
                        "producer outputs overlap; declare distinct output paths"
                    )
                targets.append(target)
                remote = relative(record["remote_path"])
                if not remote.startswith(prefix + "/"):
                    raise ValueError("artifact escapes producer namespace")
                payload = temp / f"payload-{len(pending)}"
                transfer.transfer(url(source_base, remote), payload)
                if digest(payload) != record["sha256"]:
                    raise ValueError("artifact SHA256 mismatch")
                if record["kind"] == "directory":
                    staging = temp / f"directory-{len(pending)}"
                    staging.mkdir()
                    unpack(payload, staging)
                    payload = staging
                elif record["kind"] != "file":
                    raise ValueError("unsupported artifact kind")
                pending.append((payload, target, record, producer_root))
        # All payloads and ZIP paths are checked before touching project outputs.
        for payload, target, record, producer_root in pending:
            local(producer_root, record["relative_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            shutil.move(str(payload), target)
            target.chmod(
                record.get("mode", 0o755 if target.is_dir() else 0o644) & 0o777
            )
            restored.append(record["relative_path"])
    return restored


def output(name, value):
    if file := os.environ.get("GITHUB_OUTPUT"):
        with open(file, "a", encoding="utf-8") as stream:
            stream.write(name + "=" + encode(value) + "\n")


def run_job(root, job, variant, params, no_cache=False, maintainer=False):
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", job):
        raise ValueError("job must be one PTK job name")
    if variant and ("," in variant or variant.startswith("-")):
        raise ValueError("select exactly one variant")
    if not isinstance(params, dict):
        raise TypeError("params must be a JSON object")
    command = [
        "ptk",
        *(["-V", variant] if variant else []),
        *(["--no-cache-ptk"] if no_cache else []),
        *(["maintainer"] if maintainer else []),
        "run",
        job,
    ]
    with tempfile.TemporaryDirectory(prefix="ptk-job-") as temporary:
        handoff = Path(temporary) / "result.json"
        parameter_file = Path(temporary) / "params.json"
        parameter_file.write_text(encode(params), encoding="utf-8")
        command += ["--params", str(parameter_file)]
        result = subprocess.run(
            command,
            check=False,
            cwd=root,
            env={**os.environ, "PTK_GITHUB_RESULT": str(handoff)},
        )
        if handoff.exists():
            data = json.loads(handoff.read_text(encoding="utf-8"))
            if data.get("upload_file"):
                manifest_path = Path(data["upload_file"])
                document = json.loads(manifest_path.read_text(encoding="utf-8"))
                paths = [
                    relative(item.get("relative_path")) for item in document["files"]
                ]
                # String outputs are unquoted for direct use in with: inputs.
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                    stream.write("uploads-json=" + str(manifest_path) + "\n")
                output("output-paths", paths)
            elif result.returncode == 0:
                raise ValueError(
                    data.get("upload_problem") or "job did not write an upload manifest"
                )
        elif result.returncode == 0:
            raise ValueError(
                "PTK did not return a job result; update PTK in the runner image"
            )
        return result.returncode


def main():
    def arg(name, default=""):
        return os.environ.get("PTK_ACTION_" + name.upper().replace("-", "_"), default)

    root = Path(arg("working-directory", ".")).resolve()
    mode = sys.argv[1]
    if mode == "run":
        return run_job(
            root,
            arg("job"),
            arg("variant"),
            json.loads(arg("params", "{}")),
            arg("no-cache") == "true",
            arg("maintainer") == "true",
        )
    transfer = Curl(arg("technical-user"), arg("token"))
    scope = arg("artifact-scope") or os.environ.get(
        "GITHUB_REPOSITORY", ""
    ) + "/" + os.environ.get("GITHUB_RUN_ID", "")
    if scope == "/":
        raise ValueError("artifact-scope is required outside GitHub Actions")
    if mode == "upload":
        manifest = json.loads(Path(arg("uploads-json")).read_text(encoding="utf-8"))
        address = upload(
            manifest,
            root,
            arg("base-url"),
            json.loads(arg("producer", "{}")),
            scope,
            json.loads(arg("additional-properties", "{}")),
            transfer,
        )
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("manifest-url=" + address + "\n")
    elif mode == "download":
        producers = json.loads(arg("producers", "[]"))
        needs = json.loads(arg("needs", "{}"))
        if not isinstance(producers, list) or not isinstance(needs, dict):
            raise ValueError("producers must be an array and needs an object")
        for producer in producers:
            if producer["invocation"] not in needs:
                raise ValueError("producer is not declared in GitHub needs")
        output(
            "output-paths", download(producers, root, scope, transfer, arg("base-url"))
        )
    else:
        raise ValueError("unknown action mode")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        ValueError,
        TypeError,
        OSError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"PTK action failed: {exc}", file=sys.stderr)
        sys.exit(1)
