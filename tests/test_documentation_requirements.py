"""Validate the authored requirements convention without loading reference YAML."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = {
    "feature": "FEAT_",
    "req-stkh": "REQ_Stkh_",
    "req-sys": "REQ_Sys_",
    "req-sw": "REQ_Sw_",
}
STATUS = {
    "draft",
    "under review",
    "in clarification",
    "accepted",
    "rejected",
    "obsolete",
}
STAKEHOLDER_STATUS = {
    "new/changed",
    "in clarification",
    "accepted",
    "accepted with deviation",
    "accepted with deviation agreed",
    "rejected",
    "rejected and not agreed",
    "obsolete",
}
VERIFICATION_LEVELS = {
    "req-sys": {
        "validation",
        "system-verification",
        "system-integration-verification",
        "software-verification",
        "software-integration-verification",
        "software-unit-verification",
        "review",
    },
    "req-sw": {
        "review",
        "sw-qualification-test",
        "sw-integration-test",
        "sw-component-test",
        "sw-unit-test",
    },
}
DIRECTIVE = re.compile(r"^\.\. (feature|req-stkh|req-sys|req-sw):: (.+)$", re.MULTILINE)


def records():
    result = {}
    for path in sorted((ROOT / "docs/requirements").glob("*.rst")):
        text = path.read_text(encoding="utf-8")
        starts = list(DIRECTIVE.finditer(text))
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            body = text[match.end() : end]
            attrs = dict(re.findall(r"^   :([a-z_]+): (.+)$", body, re.MULTILINE))
            identifier = attrs["id"]
            assert identifier not in result, f"Duplicate requirement ID: {identifier}"
            result[identifier] = (match[1], attrs, body, path)
    assert {item[0] for item in result.values()} == set(PREFIXES)
    return result


def test_requirement_attributes_follow_the_selected_convention():
    for identifier, (kind, attrs, body, path) in records().items():
        assert identifier.startswith(PREFIXES[kind]), (path, identifier)
        assert re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", identifier)
        if kind == "feature":
            continue
        assert attrs["safety"] == "QM", identifier
        assert attrs["security"] == attrs["legal"] == "false", identifier
        assert "**Origin:**" in body and "**Implementation:**" in body, identifier
        assert attrs["tags"] in {"implemented", "partial", "planned", "superseded"}
        if kind == "req-stkh":
            assert attrs["status_crs"] in STAKEHOLDER_STATUS, identifier
            assert attrs["safety_relevance"] == "no", identifier
            assert attrs["req_type"] in {
                "stakeholder business requirement",
                "stakeholder technical requirement",
            }, identifier
        else:
            assert attrs["status"] in STATUS, identifier
            assert attrs["req_type"] in {"functional", "non-functional", "constraint"}
            assert attrs["verification_criteria"].strip(), identifier
            assert attrs["verification_level"] in VERIFICATION_LEVELS[kind], identifier
        lifecycle = attrs.get("status", attrs.get("status_crs"))
        assert (lifecycle == "obsolete") == (attrs["tags"] == "superseded"), identifier
        if attrs["tags"] == "planned":
            assert "Not implemented" in body, identifier


def test_requirement_relations_have_valid_targets_and_no_cycles():
    needs = records()
    edges = {}
    for identifier, (kind, attrs, _, _) in needs.items():
        if kind == "feature":
            targets = [
                value.strip()
                for value in attrs.get("func_parent", "").split(",")
                if value.strip()
            ]
            assert len(targets) <= 1
            allowed = {"feature"}
        else:
            link = "clustered_by" if kind == "req-stkh" else "req_satisfies"
            targets = [
                value.strip() for value in attrs[link].split(",") if value.strip()
            ]
            allowed = {
                "req-stkh": {"feature"},
                "req-sys": {"req-stkh", "req-sys"},
                "req-sw": {"req-stkh", "req-sys", "req-sw"},
            }[kind]
            assert targets and len(targets) == len(set(targets)), identifier
            if kind == "req-stkh":
                assert len(targets) == 1, identifier
        for target in targets:
            assert target in needs and needs[target][0] in allowed, (identifier, target)
            if attrs.get("tags") != "superseded":
                assert needs[target][1].get("tags") != "superseded", (
                    identifier,
                    target,
                )
        edges[identifier] = targets

    def visit(identifier, chain):
        assert identifier not in chain, (
            f"Cyclic requirement traceability: {chain + [identifier]}"
        )
        for target in edges[identifier]:
            visit(target, chain + [identifier])

    for identifier in needs:
        visit(identifier, [])


def test_requirement_evidence_points_to_existing_sources():
    for identifier, (kind, attrs, body, _) in records().items():
        if kind not in {"req-sys", "req-sw"}:
            continue
        evidence = re.search(r"\*\*Evidence:\*\* (.+)", body)
        if attrs["tags"] == "implemented":
            assert evidence, identifier
        if not evidence:
            continue
        paths = re.findall(r"``([^`]+)``", evidence[1])
        assert paths, identifier
        for name in paths:
            path = ROOT / name
            assert path.resolve().is_relative_to(ROOT), (identifier, name)
            assert path.is_file(), (identifier, name)


def test_documentation_navigation_has_all_arc42_chapters():
    chapters = sorted((ROOT / "docs/architecture").glob("[0-9][0-9]-*.rst"))
    assert [int(path.name[:2]) for path in chapters] == list(range(1, 13))
    index = (ROOT / "docs/architecture/index.rst").read_text(encoding="utf-8")
    assert all(f"   {path.stem}\n" in index for path in chapters)
    root_index = (ROOT / "docs/index.rst").read_text(encoding="utf-8")
    for section in ("guides", "requirements", "architecture", "reference", "ci"):
        assert f"   {section}/index\n" in root_index
