"""R6P16: prove that historical fixes and every future source edit are auditable."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "diagnostics"))
from scarlet_no_repeat_gate import check_candidate, _mechanism  # noqa: E402
from scarlet_revision_coverage import (  # noqa: E402
    inspect_frozen_history, uncovered_changes, watched, verify_repo,
)
HISTORY = json.loads((ROOT / 'diagnostics/scarlet_remediation_history.json').read_text())


class RevisionCoverageTests(unittest.TestCase):
    def test_installed_p15_entries_are_present_and_frozen(self):
        self.assertEqual(inspect_frozen_history(HISTORY), [])
        self.assertEqual(HISTORY['entries'][49]['id'], 'L050')
        self.assertEqual(HISTORY['entries'][50]['id'], 'L051')
        tampered = copy.deepcopy(HISTORY)
        tampered['entries'][49]['status'] = 'device_visual_and_touch_pass'
        self.assertTrue(inspect_frozen_history(tampered))
        tampered = copy.deepcopy(HISTORY)
        del tampered['entries'][:1]
        self.assertTrue(inspect_frozen_history(tampered))

    def test_unrecorded_source_commit_rejected_even_if_ledger_is_valid(self):
        old = HISTORY['entries']
        self.assertTrue(any('UNRECORDED SOURCE COMMIT' in msg for msg in
                            uncovered_changes([('f' * 40, 'rebuild/HostApp/ScarletFullscreenSceneStack.swift')], old)))

    def test_name_only_receipt_cannot_mask_unrelated_source_file(self):
        entries = copy.deepcopy(HISTORY['entries'])
        entries.append({'id':'L052', 'source_revisions':[{'sha':'f'*40}],
                        'code_locations':[{'file':'rebuild/HostApp/Other.swift'}]})
        self.assertTrue(uncovered_changes([('f'*40,'rebuild/HostApp/ScarletFullscreenGuestTab.swift')], entries))
        self.assertFalse(uncovered_changes([('f'*40,'rebuild/HostApp/Other.swift')], entries))

    def test_p15_root_safearea_cannot_be_renamed_into_new_fix(self):
        self.assertEqual(_mechanism('guest_process_own_root_content_safearea_after_window_attachment'), 'safe_area')
        proposed = {'id':'L999', 'problem':'guest_top', 'mechanism':'safe_area',
                    'novelty':{'prior_excluded_ids':['L050'],
                               'causal_difference':'This is a new attempt to relabel prior Safe Area work without a device test.',
                               'falsifiable_prediction':'The older update is tried without a distinct measured guest view behavior.'},
                    'code_locations':[{'file':'rebuild/HostApp/Experimental.swift',
                                       'location':'@@ -0,0 +1 @@',
                                       'after':['let test = true'], 'before':[]}]}
        self.assertTrue(any('BLOCK repeated mechanism safe_area' in msg
                            for msg in check_candidate(proposed, HISTORY['entries'])))

    def test_source_watch_scope_includes_ci_and_handoff(self):
        self.assertTrue(watched('rebuild/diagnostics/SCARLET_LOG_ONLY_HANDOFF_PROMPT.md'))
        self.assertTrue(watched('.github/workflows/scarlet-paired-engines-build.yml'))
        self.assertFalse(watched('rebuild/diagnostics/scarlet_remediation_history.json'))
        self.assertFalse(watched('README.md'))

    def test_build_guard_and_report_index_wired(self):
        workflow = (ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
        recorder = (ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
        self.assertGreaterEqual(workflow.count('--repository-check'), 2)
        self.assertGreaterEqual(workflow.count('fetch-depth: 0'), 2)
        self.assertIn('for attempt in entries {', recorder)
        self.assertNotIn('for attempt in entries.suffix(18)', recorder)
        self.assertIn('rebuild/diagnostics/scarlet_remediation_history.json',
                      (ROOT/'integration/apply_scarlet_host.py').read_text())

    def test_actual_branch_commits_have_receipts(self):
        # On the P15 anchor, no later commits exist; after R6P16's final
        # ledger update, every source edit must have an exact commit receipt.
        self.assertEqual(verify_repo(HISTORY, ROOT.parent), [])


if __name__ == '__main__':
    unittest.main()
