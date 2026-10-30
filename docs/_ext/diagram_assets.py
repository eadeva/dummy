"""Render editable PlantUML sources and reject stale checked-in SVGs."""

import argparse
import hashlib
import os
import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree

DOCS = Path(__file__).resolve().parents[1]
VERSION = "1.2026.9"
JAR_SHA256 = "aa4a1d06f8911c4b842beff4828dd955be431692b631a312d04c0e9fab9581de"
STAMP = re.compile(r"<!-- PTK PlantUML source=([a-f0-9]{64}) svg=([a-f0-9]{64}) -->\n")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def diagrams():
    return sorted((DOCS / "diagrams").glob("*.puml"))


def source_digest(source):
    return digest(VERSION + "\n" + source.read_text(encoding="utf-8"))


def verify():
    for source in diagrams():
        target = DOCS / "_static/diagrams" / source.with_suffix(".svg").name
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        stamp = STAMP.match(text)
        if (
            not stamp
            or stamp[1] != source_digest(source)
            or stamp[2] != digest(text[stamp.end() :])
        ):
            raise ValueError(
                f"Missing or stale diagram: {target.name}. "
                "Regenerate with python docs/_ext/diagram_assets.py --jar PATH_TO_PLANTUML_JAR."
            )
        ElementTree.fromstring(text[stamp.end() :])


def render(jar):
    if hashlib.sha256(jar.read_bytes()).hexdigest() != JAR_SHA256:
        raise ValueError(
            f"Use the official PlantUML {VERSION} plantuml.jar (see development guide)."
        )
    for source in diagrams():
        result = subprocess.run(
            [
                "java",
                "-Djava.awt.headless=true",
                "-jar",
                str(jar.resolve()),
                "-tsvg",
                "-charset",
                "UTF-8",
                "-pipe",
            ],
            input=source.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PLANTUML_SECURITY_PROFILE": "SANDBOX"},
            timeout=60,
            check=True,
        )
        ElementTree.fromstring(result.stdout)
        svg = result.stdout.rstrip() + "\n"
        stamp = (
            f"<!-- PTK PlantUML source={source_digest(source)} svg={digest(svg)} -->\n"
        )
        target = DOCS / "_static/diagrams" / source.with_suffix(".svg").name
        target.write_text(stamp + svg, encoding="utf-8", newline="\n")
    verify()


def setup(app):
    def check_assets(app):
        from sphinx.errors import ExtensionError

        try:
            verify()
        except (ValueError, OSError, ElementTree.ParseError) as exc:
            raise ExtensionError(str(exc)) from exc

    app.connect("builder-inited", check_assets)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jar",
        type=Path,
        help=f"Regenerate with the official PlantUML {VERSION} JAR; Java is required.",
    )
    args = parser.parse_args()
    if args.jar:
        render(args.jar)
    else:
        verify()
    print(f"Verified {len(diagrams())} PlantUML diagrams.")
