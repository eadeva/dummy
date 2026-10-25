"""Keep the published skill catalog complete and its source links usable."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_plan_skills_are_shipped_and_documented():
    planned = set(re.findall(r"`(ptk-[a-z-]+)`", (ROOT / "docs/PLAN.md").read_text()))
    paths = list((ROOT / ".claude/skills").glob("*/SKILL.md"))
    assert {p.parent.name for p in paths} == planned
    catalog = (ROOT / "docs/skills.rst").read_text()
    for path in paths:
        _, frontmatter, body = path.read_text().split("---", 2)
        metadata = yaml.safe_load(frontmatter)
        assert metadata["name"] == path.parent.name
        assert metadata["description"]
        assert path.parent.name in catalog
        for reference in re.findall(r"`((?:src/|docs/|tests/)[^`]+)`", body):
            assert (ROOT / reference).exists(), (path, reference)
