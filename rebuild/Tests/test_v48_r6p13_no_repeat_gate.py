"""R6P13: prevent source-equivalent repeated fixes from reaching iOS builds."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "diagnostics"))
from scarlet_no_repeat_gate import check_candidate, validate  # noqa: E402

HISTORY = json.loads((ROOT / "diagnostics/scarlet_remediation_history.json")
                     .read_text(encoding="utf-8"))


def proposed(mechanism="independent_new_mechanism"):
    return {
        "id": "L999", "problem": "guest_top", "mechanism": mechanism,
        "novelty": {
            "prior_excluded_ids": ["L035", "L043", "L046"],
            "causal_difference": "This probes a separately demonstrated root cause, not previously adjusted scene geometry.",
            "falsifiable_prediction": "A new guest-side observation must differ while previous host inset readbacks remain identical."
        }, "code_locations": [{
            "file": "rebuild/HostApp/FutureIsolatedFix.swift",
            "location": "@@ -1,0 +1,1 @@",
            "before": [], "after": ["let neverBeforeTested = 7"]
        }]
    }


class NoRepeatContract(unittest.TestCase):
    def test_existing_archive_and_new_metadata_pass(self):
        self.assertEqual(validate(HISTORY), [])

    def test_repeated_safe_area_without_new_evidence_is_rejected(self):
        p = proposed("safe_area")
        errs = check_candidate(p, HISTORY["entries"])
        self.assertTrue(any("BLOCK repeated mechanism" in s for s in errs), errs)

    def test_alias_renaming_cannot_reopen_old_safe_area(self):
        p = proposed("fbscene_safe_insets")
        errs = check_candidate(p, HISTORY["entries"])
        self.assertTrue(any("BLOCK repeated mechanism" in s for s in errs), errs)

    def test_new_mechanism_with_causal_test_is_eligible(self):
        self.assertEqual(check_candidate(proposed(), HISTORY["entries"]), [])

    def test_same_exact_source_change_is_rejected_even_when_renamed(self):
        old = next(e for e in HISTORY["entries"]
                   if e.get("code_locations") and e["problem"] == "guest_top")
        p = proposed()
        p["code_locations"] = [copy.deepcopy(old["code_locations"][0])]
        errs = check_candidate(p, HISTORY["entries"])
        self.assertTrue(any("duplicate source change" in s for s in errs), errs)

    def test_export_index_precedes_verbose_jsonl(self):
        source = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
        export = source.split("    func makeShareFile(includeHistory:", 1)[1]
        self.assertIn("NO-REPEAT DECISION INDEX", export)
        self.assertLess(export.index("Self.remediationDecisionIndex()"),
                        export.index("for index in indices"))
        self.assertIn("entries.suffix(18)", source)
        self.assertIn('body += Self.decodedAudit(Self.remediationHistoryBlob)', source)
        self.assertIn('body += Self.decodedAudit(Self.handoffPromptBlob)', source)

    def test_novelty_must_be_explained_not_empty(self):
        p = proposed()
        p["novelty"] = {}
        self.assertTrue(check_candidate(p, HISTORY["entries"]))


if __name__ == "__main__":
    unittest.main()
