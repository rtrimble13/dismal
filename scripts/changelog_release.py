#!/usr/bin/env python3
"""Move the "Unreleased" section of CHANGELOG.md under a new version heading.

Usage: changelog_release.py vX.Y.Z [path/to/CHANGELOG.md]
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    tag = argv[0]
    version = tag[1:] if tag.startswith("v") else tag
    path = Path(argv[1] if len(argv) > 1 else "CHANGELOG.md")
    text = path.read_text(encoding="utf-8")
    if not UNRELEASED_RE.search(text):
        raise SystemExit("CHANGELOG.md has no '## [Unreleased]' section")
    today = dt.date.today().isoformat()
    replacement = f"## [Unreleased]\n\n## [{version}] - {today}"
    new_text = UNRELEASED_RE.sub(replacement, text, count=1)
    path.write_text(new_text, encoding="utf-8")
    print(f"CHANGELOG.md: released {version} ({today})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
