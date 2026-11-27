#!/usr/bin/env python3
"""Tests for the shared helper module and its per-skill copies."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import openmining_common as common  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover - environment dependent
    jsonschema = None


class CommonSyncTests(unittest.TestCase):
    def test_every_skill_has_an_identical_copy(self):
        source = (ROOT / "shared" / "openmining_common.py").read_bytes()
        skills = sorted(ROOT.glob("mine-*"))
        self.assertEqual(len(skills), 17)
        for skill in skills:
            copy = skill / "scripts" / "common.py"
            self.assertTrue(copy.is_file(), f"missing {copy}")
            self.assertEqual(
                copy.read_bytes(),
                source,
                f"{copy} is stale; run python3 tools/sync_common.py",
            )


class StatusTests(unittest.TestCase):
    def test_native_statuses_map_to_the_unified_enum(self):
        cases = {
            "ok": "PASS",
            "READY": "PASS",
            "PASS": "PASS",
            "PASS_WITH_WARNINGS": "PASS_WITH_WARNINGS",
            "invalid": "FAIL",
            "FAILED": "FAIL",
            "BROKEN": "FAIL",
            "UNKNOWN": "UNKNOWN",
            "EMPTY": "UNKNOWN",
            "UNSUPPORTED": "UNSUPPORTED",
        }
        for native, expected in cases.items():
            self.assertEqual(common.normalize_status(native), expected, native)

    def test_unknown_status_is_not_mapped(self):
        self.assertIsNone(common.normalize_status("SOMETHING_ELSE"))
        self.assertIsNone(common.normalize_status(None))

    def test_finalize_report_is_additive(self):
        report = {"skill": "custom", "status": "ok", "summary": {"errors": 0}}
        original = json.loads(json.dumps(report))
        common.finalize_report(report, "mine-example")
        self.assertEqual(report["schemaVersion"], common.SCHEMA_VERSION)
        self.assertEqual(report["skill"], "custom")
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["summary"], original["summary"])
        self.assertEqual(report["status"], "ok")

    def test_finalize_report_adds_skill_when_missing(self):
        report = {"status": "FAILED"}
        common.finalize_report(report, "mine-example")
        self.assertEqual(report["skill"], "mine-example")
        self.assertEqual(report["result"], "FAIL")

    def test_finalize_report_leaves_data_reports_without_result(self):
        report = {"point_count": 3}
        common.finalize_report(report, "mine-example")
        self.assertNotIn("result", report)
        self.assertEqual(report["schemaVersion"], common.SCHEMA_VERSION)

    @unittest.skipUnless(jsonschema is not None, "jsonschema is not installed")
    def test_finalized_reports_validate_against_the_envelope(self):
        schema = json.loads(
            (ROOT / "shared" / "schemas" / "report-envelope.schema.json").read_text(
                encoding="utf-8"
            )
        )
        report = common.finalize_report(
            {
                "status": "PASS_WITH_WARNINGS",
                "issues": [
                    {"severity": "warning", "code": "DEMO", "message": "demo issue"}
                ],
            },
            "mine-example",
        )
        jsonschema.validate(report, schema)


class HelperTests(unittest.TestCase):
    def test_number_helpers_have_distinct_contracts(self):
        self.assertTrue(common.is_number(1))
        self.assertFalse(common.is_number(True))
        self.assertFalse(common.is_number("1"))
        self.assertTrue(common.is_numeric_text("1.5"))
        self.assertTrue(common.is_numeric_text("nan"))
        self.assertFalse(common.is_numeric_text("x"))
        self.assertTrue(common.is_finite_number(1.5))
        self.assertFalse(common.is_finite_number(float("nan")))

    def test_formatters_keep_their_expected_precision(self):
        self.assertEqual(common.fmt(1.23456), "1.2346")
        self.assertEqual(common.fmt_basic(1.23456), "1.235")
        self.assertEqual(common.fmt(None), "-")

    def test_read_jsonl_keeps_malformed_lines(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"a": 1}\nnot-json\n[]\n', encoding="utf-8")
            records = common.read_jsonl(path, kind="Event line")
        self.assertEqual(records[0]["a"], 1)
        self.assertIn("Invalid JSON", records[1]["_parse_error"])
        self.assertEqual(records[2]["_parse_error"], "Event line is not a JSON object.")


if __name__ == "__main__":
    unittest.main()
