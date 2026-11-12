"""R6P10: code-level fix provenance must travel with every iPhone report.

Regression against repeatedly claiming the same safe-area/UIKit/overlay patch
is a new solution. Missing historical source locations are explicitly labeled
instead of fabricating old project paths.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "diagnostics/scarlet_remediation_history.json"
PROMPT = ROOT / "diagnostics/SCARLET_LOG_ONLY_HANDOFF_PROMPT.md"
REC = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
INTEGRATION = (ROOT / "integration/apply_scarlet_host.py").read_text()

class CodeLevelHistoryArchive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = json.loads(HISTORY.read_text(encoding="utf-8"))
        cls.p = PROMPT.read_text(encoding="utf-8")

    def test_prior_records_are_immutable_and_not_truncated(self):
        entries = self.h["entries"]
        self.assertGreaterEqual(len(entries), 45)
        self.assertGreaterEqual(self.h["schema"], 2)
        ids = [x["id"] for x in entries]
        self.assertEqual(ids[:45], [f"L{i:03}" for i in range(1, 46)])
        self.assertEqual(len(ids), len(set(ids)))

    def test_verified_entries_have_real_before_and_after_source_diff(self):
        verified = 0
        for item in self.h["entries"]:
            self.assertIn(item["source_verification"],
                ("git_patch_observed", "source_unavailable",
                 "commit_without_mapped_source_diff"))
            self.assertIn("code_locations", item)
            self.assertIn("repeat_policy", item)
            self.assertIn("mechanism", item)
            if item["source_verification"] == "git_patch_observed":
                verified += 1
                self.assertTrue(item["code_locations"], item["id"])
                self.assertTrue(item["source_revisions"], item["id"])
                for loc in item["code_locations"]:
                    self.assertTrue(loc["file"].startswith("rebuild/"),
                                    (item["id"], loc["file"]))
                    self.assertTrue(loc["location"].startswith("@@ "),
                                    (item["id"], loc["location"]))
                    self.assertTrue(loc["before"] or loc["after"], item["id"])
                    self.assertRegex(loc["commit"], r"^[a-f0-9]{40}$")
            elif item["source_verification"] == "source_unavailable":
                self.assertFalse(item["code_locations"], item["id"])
        self.assertGreaterEqual(verified, 28)

    def test_safe_area_and_startup_order_known_fixes_are_explicit(self):
        by_id = {x["id"]: x for x in self.h["entries"]}
        for key in ("L028", "L029", "L031", "L032", "L033",
                    "L035", "L040", "L041", "L043", "L045"):
            with self.subTest(entry=key):
                e = by_id[key]
                self.assertEqual(e["source_verification"], "git_patch_observed")
                self.assertTrue(e["code_locations"])

    def test_export_embeds_complete_json_and_literal_handoff_prompt(self):
        self.assertIn("===== REMEDIATION HISTORY · FILE/FUNCTION/BEFORE/AFTER DIFF =====", REC)
        self.assertIn("===== NO-REPEAT POLICY & AI HANDOFF PROMPT =====", REC)
        self.assertIn("__SCARLET_REMEDIATION_HISTORY_B64__", REC)
        self.assertIn("__SCARLET_HANDOFF_PROMPT_B64__", REC)
        self.assertIn('history_path.read_bytes()', INTEGRATION)
        self.assertIn('handoff_path.read_bytes()', INTEGRATION)
        self.assertIn("base64.b64encode(source_bytes)", INTEGRATION)
        self.assertIn("Repair history contains duplicate IDs", INTEGRATION)
        self.assertIn("Source-verified entry missing source diff", INTEGRATION)
        self.assertIn("recorder.write_text(r, encoding=\"utf-8\")", INTEGRATION)
        self.assertIn("try body.write(to: file, atomically: true, encoding: .utf8)", REC)

    def test_prompt_requires_exact_locations_and_code_diff(self):
        for phrase in (
            "code_locations", "source_revisions", "before", "after",
            "rollback_commit", "source_unavailable", "중복", "Xcode",
            "CURRENT RUN", "REMEDIATION HISTORY",
        ):
            self.assertIn(phrase, self.p)
        self.assertIn("f29ddd833305", self.p)

    def test_no_credentials_or_per_app_names_in_history(self):
        body = HISTORY.read_text(encoding="utf-8")
        for forbidden in ("Apple ID:", "password=", "otp=", "UDID="):
            self.assertNotIn(forbidden, body)

if __name__ == "__main__":
    unittest.main()
