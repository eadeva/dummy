"""Read tool results that steps leave in their reports folder.

Recognised by content, not name: JUnit XML (``<testsuite>``/``<testsuites>``),
Cobertura XML (``<coverage>``) and SARIF JSON (``*.sarif``, ``*.sarif.json``).
Files directly in the action's reports folder are ptk's own output and ignored.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

from ...domain.layout import safe
from ...domain.reporting.model import (
    ERROR,
    FAILED,
    PASSED,
    SKIPPED,
    Contribution,
    Coverage,
    Finding,
    TestCase,
    TestSuite,
)


def _float(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def parse_junit(root: ET.Element, step: str, source: str) -> list[TestSuite]:
    suites_xml = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
    suites = []
    for suite_xml in suites_xml:
        suite = TestSuite(name=suite_xml.get("name", source), step=step, source=source)
        for case in suite_xml.findall("testcase"):
            status, message = PASSED, ""
            for tag, kind in (
                ("failure", FAILED),
                ("error", ERROR),
                ("skipped", SKIPPED),
            ):
                node = case.find(tag)
                if node is not None:
                    status = kind
                    message = (node.get("message") or node.text or "").strip()
                    break
            suite.cases.append(
                TestCase(
                    name=case.get("name", "?"),
                    classname=case.get("classname", ""),
                    status=status,
                    time=_float(case.get("time")),
                    message=message[:2000],
                )
            )
        suites.append(suite)
    return suites


def parse_cobertura(root: ET.Element, step: str, source: str) -> list[Coverage]:
    valid = root.get("lines-valid")
    covered = root.get("lines-covered")
    if valid is not None and covered is not None:
        return [Coverage(step, source, int(_float(valid)), int(_float(covered)))]
    rate = _float(root.get("line-rate"))
    return [Coverage(step, source, 1000, round(rate * 1000))]


def parse_sarif(data: dict, step: str) -> list[Finding]:
    findings = []
    for run in data.get("runs", []):
        tool = run.get("tool", {}).get("driver", {}).get("name", "sarif")
        for result in run.get("results", []):
            location = (result.get("locations") or [{}])[0].get("physicalLocation", {})
            region = location.get("region", {})
            findings.append(
                Finding(
                    tool=tool,
                    rule=result.get("ruleId", ""),
                    level=result.get("level", "warning"),
                    message=(result.get("message", {}).get("text") or "").strip()[
                        :2000
                    ],
                    file=location.get("artifactLocation", {}).get("uri", ""),
                    line=region.get("startLine"),
                    step=step,
                )
            )
    return findings


def scan(reports_dir: Path, steps: Mapping[str, str]) -> list[Contribution]:
    """``steps``: folder path below ``reports_dir`` (as written by the layout) -> label."""
    contributions: dict[str, Contribution] = {}
    if not reports_dir.is_dir():
        return []
    for file in sorted(reports_dir.rglob("*")):
        if not file.is_file() or file.parent == reports_dir:
            continue
        rel = file.parent.relative_to(reports_dir).as_posix()
        step = steps.get(rel)
        if step is None:
            continue
        contribution = contributions.setdefault(step, Contribution(step))
        name = file.name.lower()
        try:
            if name.endswith((".sarif", ".sarif.json")):
                data = json.loads(file.read_text(encoding="utf-8"))
                contribution.findings += parse_sarif(data, step)
            elif name.endswith(".xml"):
                root = ET.parse(file).getroot()
                if root.tag in ("testsuite", "testsuites"):
                    contribution.suites += parse_junit(root, step, file.name)
                elif root.tag == "coverage":
                    contribution.coverage += parse_cobertura(root, step, file.name)
        except (ET.ParseError, ValueError, OSError) as exc:
            contribution.problems.append(f"{step}: cannot read {file.name}: {exc}")
    return list(contributions.values())


def step_folders(labels: list[str]) -> dict[str, str]:
    return {
        "/".join(safe(part) for part in label.split("/")): label for label in labels
    }
