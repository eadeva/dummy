"""Preserve user settings while updating a marked shell-completion block."""

import codecs
import os
import re
import stat
import tempfile
from pathlib import Path

START = "# >>> PTK completion >>>"
END = "# <<< PTK completion <<<"


def _decode(raw):
    # BOM-less UTF-8 and ANSI profiles both round-trip without altering bytes.
    for bom, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF8, "utf-8"),
    ):
        if raw.startswith(bom):
            return raw[len(bom) :].decode(encoding), encoding, bom
    try:
        return raw.decode("utf-8"), "utf-8", b""
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1", b""


def update_profile(profile: Path, source: str | None, *, dry_run: bool = False) -> bool:
    """Replace only our marked block; None removes it. Return whether changed."""
    profile = profile.expanduser().resolve()
    exists = profile.exists()
    original = profile.read_bytes() if exists else b""
    text, encoding, bom = _decode(original)
    markers = []
    for marker in (START, END):
        markers.append(
            list(re.finditer(r"(?m)^" + re.escape(marker) + r"\r?$(?:\n)?", text))
        )
    starts, ends = markers
    if starts or ends:
        if len(starts) != 1 or len(ends) != 1 or starts[0].start() >= ends[0].start():
            raise ValueError(
                "incomplete or duplicate PTK completion markers; profile left unchanged"
            )
        before, after = text[: starts[0].start()], text[ends[0].end() :]
    else:
        if source is None:
            return False
        before, after = text, ""
    newline = "\r\n" if "\r\n" in text else "\n"
    block = ""
    if source is not None:
        block = newline.join([START, *source.splitlines(), END, ""])
        if before and not before.endswith(("\n", "\r")):
            before += newline
    result = bom + (before + block + after).encode(encoding)
    if result == original:
        return False
    if dry_run:
        return True
    profile.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        try:
            with profile.with_name(profile.name + ".ptk.bak").open("xb") as backup:
                backup.write(original)
            Path(backup.name).chmod(stat.S_IMODE(profile.stat().st_mode))
        except FileExistsError:
            pass  # Keep the original pre-install profile on repeated updates.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=profile.parent, delete=False) as target:
            temporary = Path(target.name)
            target.write(result)
        if exists:
            temporary.chmod(stat.S_IMODE(profile.stat().st_mode))
        os.replace(temporary, profile)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True
