#!/usr/bin/env python3
"""Print the CHANGELOG.md section for one version (used for GitHub release notes).

Usage: changelog_section.py X.Y.Z [path/to/CHANGELOG.md]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    version = argv[0].lstrip("v")
    path = Path(argv[1] if len(argv) > 1 else "CHANGELOG.md")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", re.MULTILINE | re.DOTALL
    )
    m = pattern.search(text)
    if not m or not m.group(1).strip():
        raise SystemExit(f"no changelog section for {version}")
    print(m.group(1).strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
