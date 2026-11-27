"""Shared helpers for Open Mining Skills.

This file is the single source of truth for the helper module copied into every
skill as ``scripts/common.py``. Edit this file, then run:

    python3 tools/sync_common.py

The copies must stay byte-identical so each skill directory remains
self-contained and can still be copied or symlinked on its own.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1"

STATUS_PASS = "PASS"
STATUS_PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_UNSUPPORTED = "UNSUPPORTED"
STATUS_VALUES = frozenset(
    {
        STATUS_PASS,
        STATUS_PASS_WITH_WARNINGS,
        STATUS_FAIL,
        STATUS_UNKNOWN,
        STATUS_UNSUPPORTED,
    }
)

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2

_STATUS_ALIASES = {
    "ok": STATUS_PASS,
    "ready": STATUS_PASS,
    "pass": STATUS_PASS,
    "pass_with_warnings": STATUS_PASS_WITH_WARNINGS,
    "warning": STATUS_PASS_WITH_WARNINGS,
    "invalid": STATUS_FAIL,
    "failed": STATUS_FAIL,
    "fail": STATUS_FAIL,
    "broken": STATUS_FAIL,
    "unknown": STATUS_UNKNOWN,
    "empty": STATUS_UNKNOWN,
    "unsupported": STATUS_UNSUPPORTED,
}


def normalize_status(value: Any) -> str | None:
    """Map a skill-specific status string to the unified result enum."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.upper() in STATUS_VALUES:
        return text.upper()
    return _STATUS_ALIASES.get(text.lower())


def finalize_report(
    report: dict,
    skill: str,
    status: Any = None,
    *,
    schema_version: str = SCHEMA_VERSION,
) -> dict:
    """Add common report metadata without changing existing fields.

    ``status`` overrides ``report["status"]`` when given. ``result`` is only
    added when the native status can be mapped to the unified enum, so report
    types that are not pass/fail decisions remain unchanged apart from
    ``schemaVersion`` and ``skill``.
    """
    if not isinstance(report, dict):
        return report
    report.setdefault("schemaVersion", schema_version)
    report.setdefault("skill", skill)
    native = status if status is not None else report.get("status")
    result = normalize_status(native)
    if result is not None:
        report.setdefault("result", result)
    return report


def file_sha256(path: str | os.PathLike[str], chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_manifest(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Return a small provenance manifest for a source file."""
    p = Path(path)
    return {
        "path": str(p.resolve()),
        "name": p.name,
        "size_bytes": p.stat().st_size,
        "sha256": file_sha256(p),
    }


def read_text(
    path: str | os.PathLike[str], encoding: str | None = None
) -> tuple[str, str]:
    """Read a text file, trying common encodings when none is given."""
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "gbk", "latin-1"]
    for enc in encodings:
        if not enc:
            continue
        try:
            return Path(path).read_text(encoding=enc), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Unable to decode file: {path}")


def load_json(path: str | os.PathLike[str]) -> Any:
    """Read a JSON file, raising a user-facing SystemExit on failure."""
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise SystemExit(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read {path}: {exc}") from exc


def read_json(path: str | os.PathLike[str]) -> Any:
    """Read a JSON file, raising a user-facing SystemExit on failure."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SystemExit(f"Unable to read {source}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {source}: {exc}") from exc


def read_jsonl(path: str | os.PathLike[str], kind: str = "Line") -> list[dict]:
    """Read JSON Lines, keeping malformed lines as parse-error records.

    ``kind`` is used in the error record, e.g. ``"Event line"``.
    """
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SystemExit(f"Unable to read {source}: {exc}") from exc
    records: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            records.append({"_line": lineno, "_parse_error": f"Invalid JSON: {exc}"})
            continue
        if not isinstance(value, dict):
            records.append(
                {"_line": lineno, "_parse_error": f"{kind} is not a JSON object."}
            )
            continue
        record = dict(value)
        record.setdefault("_line", lineno)
        records.append(record)
    return records


def write_json(path: str | os.PathLike[str], data: Any) -> None:
    """Write JSON with a trailing newline, creating parent directories."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_text(path: str | os.PathLike[str], text: str) -> None:
    """Write UTF-8 text, creating parent directories."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def fmt(value: float | int | None, digits: int = 4) -> str:
    """Format a number for reports; very small values use scientific notation."""
    if value is None:
        return "-"
    if isinstance(value, float):
        if value != 0.0 and abs(value) < 10 ** (-digits):
            return f"{value:.2e}"
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def fmt_basic(value: float | int | None) -> str:
    """Format a number with at most three decimals for compact human reports."""
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def detect_delimiter(lines: list[str]) -> str | None:
    """Return the most frequent delimiter among ``,``, ``;`` and tab."""
    candidates = {",": 0, ";": 0, "\t": 0}
    for line in lines:
        for delimiter in candidates:
            candidates[delimiter] += line.count(delimiter)
    best = max(candidates, key=candidates.get)
    return best if candidates[best] > 0 else None


def split_line(line: str, delimiter: str | None) -> list[str]:
    """Split a line on a delimiter, or on whitespace when delimiter is None."""
    if delimiter is None:
        return line.split()
    return [cell.strip() for cell in line.split(delimiter)]


def is_number(value: Any) -> bool:
    """Return True for JSON numbers (int/float), excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_numeric_text(value: str) -> bool:
    """Return True when a text cell can be parsed as a float."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def is_finite_number(value: Any) -> bool:
    """Return True for finite JSON numbers, excluding booleans."""
    return is_number(value) and math.isfinite(float(value))


def as_id(value: Any) -> str | None:
    """Return a non-empty identifier as a string, or None when invalid.

    Numeric IDs used by the database design are accepted and normalised to
    strings so that cross-file comparisons are type-stable.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def as_bool(value: Any) -> bool | None:
    """Return a boolean value unchanged, or None for non-booleans."""
    return value if isinstance(value, bool) else None


def add_issue(
    issues: list[dict],
    severity: str,
    code: str,
    message: str,
    **context: Any,
) -> None:
    """Append an issue, omitting context keys whose value is None."""
    issue = {"severity": severity, "code": code, "message": message}
    for key, value in context.items():
        if value is not None:
            issue[key] = value
    issues.append(issue)


def magnitude_clue(min_x: float, min_y: float, max_x: float, max_y: float) -> str:
    """Return a coarse coordinate clue based on the data extents.

    This is deliberately conservative: it never identifies a CRS, it only
    flags which family of coordinates the values resemble.
    """
    abs_max = max(abs(v) for v in (min_x, min_y, max_x, max_y))
    in_degree_range = (
        -180.0 <= min_x <= max_x <= 180.0
        and -90.0 <= min_y <= max_y <= 90.0
    )
    if in_degree_range:
        return "DEGREE_CANDIDATE"
    if abs_max >= 100000.0:
        return "PROJECTED_METER_CANDIDATE"
    return "LOCAL_OR_UNKNOWN"
