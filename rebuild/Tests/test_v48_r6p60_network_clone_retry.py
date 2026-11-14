"""Protect P60 pinned native compilation from transient GitHub DNS outages."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
WF=(R.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
class P60PinnedCheckoutRetry(unittest.TestCase):
    def test_all_three_upstream_clones_are_bounded_and_pinned(self):
        for repo in ('LiveContainer/LiveContainer','LiveContainer/SideStore','StikDebug/StikPair'):
            self.assertIn('if git clone --filter=blob:none https://github.com/'+repo+'.git ',WF)
        self.assertEqual(WF.count('for attempt in 1 2 3 4; do'),5)
        self.assertEqual(WF.count('if [ "$attempt" -eq 4 ]; then'),5)
        self.assertEqual(WF.count('sleep "$((attempt*5))"'),5)
        self.assertIn('test "$(git -C engine/LiveContainer rev-parse HEAD)" = "$pin"',WF)
        self.assertIn('EMBEDDED_SIDESTORE_REF',WF)
        self.assertIn('7c911d8319dc5bcc411bf299d963689e26009b0b',WF)
    def test_submodules_retry_without_deleting_signed_assets(self):
        for repo in ('engine/LiveContainer','engine/SideStore'):
            self.assertIn('if git -C '+repo+' submodule update --init --recursive --jobs 3; then break; fi',WF)
        self.assertNotIn('rm -rf "$GITHUB_WORKSPACE"',WF)
        self.assertNotIn('rm -rf "$RUNNER_TEMP"',WF)
        self.assertNotIn('rm -rf ~/Library',WF)

if __name__=="__main__":unittest.main()
