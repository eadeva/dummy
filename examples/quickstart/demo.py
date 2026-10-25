"""Small offline workload for the quickstart; no third-party dependencies."""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    mode = sys.argv[1]
    artifact = Path(os.environ["PTK_BIN_DIR"]) / "message.txt"
    if mode == "prepare":
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(sys.argv[2], encoding="utf-8")
        print(f"Created {artifact}")
    elif mode == "test":
        passed = artifact.read_text(encoding="utf-8") == sys.argv[2]
        suite = ET.Element("testsuite", name="quickstart")
        case = ET.SubElement(suite, "testcase", name="artifact matches parameter")
        if not passed:
            ET.SubElement(case, "failure", message="artifact content differs")
        reports = Path(os.environ["PTK_STEP_REPORTS_DIR"])
        reports.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(suite).write(reports / "results.xml", encoding="utf-8")
        print(f"Artifact check: {'passed' if passed else 'failed'}")
        return 0 if passed else 1
    elif mode == "extra":
        print("Extra checks enabled for this variant")
    else:
        raise ValueError(f"Unknown demo mode: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
