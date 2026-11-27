#!/usr/bin/env python3
"""Sync the canonical shared helper module to every skill.

Each skill keeps its own ``scripts/common.py`` so a skill directory can still
be copied or symlinked on its own. The copies are generated from
``shared/openmining_common.py`` and must stay byte-identical.

Usage:
    python3 tools/sync_common.py          # rewrite all copies
    python3 tools/sync_common.py --check  # exit 1 when a copy is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shared" / "openmining_common.py"


def targets() -> list[Path]:
    """Return every skill's scripts/common.py path, sorted."""
    return sorted(
        skill / "scripts" / "common.py"
        for skill in ROOT.glob("mine-*")
        if (skill / "scripts").is_dir()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync shared/openmining_common.py to every skill."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify copies; exit 1 when any copy differs.",
    )
    args = parser.parse_args(argv)

    if not SOURCE.is_file():
        print(f"Missing canonical module: {SOURCE}", file=sys.stderr)
        return 2

    source_bytes = SOURCE.read_bytes()
    copies = targets()
    stale: list[Path] = []

    for target in copies:
        if args.check:
            if not target.is_file() or target.read_bytes() != source_bytes:
                stale.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_bytes)
        print(f"synced {target.relative_to(ROOT)}")

    if args.check:
        if stale:
            print("common.py copies are out of date:", file=sys.stderr)
            for target in stale:
                print(f"  {target.relative_to(ROOT)}", file=sys.stderr)
            print("Run: python3 tools/sync_common.py", file=sys.stderr)
            return 1
        print(
            f"all {len(copies)} common.py copies match "
            "shared/openmining_common.py"
        )
        return 0

    print(f"synced {len(copies)} skill(s) from shared/openmining_common.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
