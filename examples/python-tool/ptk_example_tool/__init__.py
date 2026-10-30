"""A reusable command with no dependency on PTK's Python interfaces."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Check that a project input exists")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if not args.path.is_file():
        parser.exit(1, f"Required file is missing: {args.path}\n")
    print(f"Required file exists: {args.path}")
    return 0
