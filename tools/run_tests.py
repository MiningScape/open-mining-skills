#!/usr/bin/env python3
"""Run the shared tests and every skill's unittest suite.

Usage:
    python3 tools/run_tests.py
    python3 tools/run_tests.py --fail-fast
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, cwd: Path, args: list[str]) -> tuple[str, int, str]:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    output = (result.stdout + result.stderr).strip()
    return label, result.returncode, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all Open Mining Skills tests.")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)

    checks: list[tuple[str, Path, list[str]]] = [
        (
            "common.py sync",
            ROOT,
            ["tools/sync_common.py", "--check"],
        ),
        (
            "shared tests",
            ROOT,
            ["-m", "unittest", "discover", "-s", "shared/tests"],
        ),
    ]
    for skill in sorted(ROOT.glob("mine-*")):
        if (skill / "tests").is_dir():
            checks.append(
                (
                    skill.name,
                    skill,
                    ["-m", "unittest", "discover", "-s", "tests"],
                )
            )

    failures: list[str] = []
    for label, cwd, command in checks:
        name, code, output = run(label, cwd, command)
        tail = output.splitlines()[-1] if output else ""
        print(f"[{'PASS' if code == 0 else 'FAIL'}] {name}: {tail}")
        if code != 0:
            failures.append(name)
            print(output)
            print()
            if args.fail_fast:
                break

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print(f"All {len(checks)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
