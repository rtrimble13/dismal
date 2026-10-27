#!/usr/bin/env python3
"""Compute the next vMAJOR.MINOR.PATCH tag from the repository's git tags.

Usage:
    next_version.py [patch|minor|major]   # print the next tag (default: patch)
    next_version.py --current             # print the latest existing tag (v0.0.0 if none)
"""

from __future__ import annotations

import re
import subprocess
import sys

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def existing_tags() -> list[tuple[int, int, int]]:
    out = subprocess.run(["git", "tag", "--list", "v*"], check=True, capture_output=True, text=True)
    versions = []
    for line in out.stdout.split():
        m = TAG_RE.match(line.strip())
        if m:
            versions.append(tuple(int(x) for x in m.groups()))
    return sorted(versions)  # type: ignore[arg-type]


def current() -> tuple[int, int, int]:
    tags = existing_tags()
    return tags[-1] if tags else (0, 0, 0)


def bump(version: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if part == "major":
        return (major + 1, 0, 0)
    if part == "minor":
        return (major, minor + 1, 0)
    if part == "patch":
        return (major, minor, patch + 1)
    raise SystemExit(f"unknown bump part {part!r}; use patch, minor or major")


def fmt(version: tuple[int, int, int]) -> str:
    return "v{}.{}.{}".format(*version)


def main(argv: list[str]) -> int:
    if "--current" in argv:
        print(fmt(current()))
        return 0
    part = argv[0] if argv else "patch"
    print(fmt(bump(current(), part)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
