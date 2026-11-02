"""Regression: Setup must never call unknown unobserved status 'missing'.

SideStore's network handshake can fail while an existing 10KB pairing file and
certificate remain stored. All prerequisites must not display as missing
before the authoritative host status snapshot settles.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "scripts/templates/v3_unified_shell.swift"

class V176SetupAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SHELL.read_text(encoding="utf-8")
        cls.store = cls.source[cls.source.index("final class V3SetupStore"):cls.source.index("struct V3SetupAssistantView")]
        cls.view = cls.source[cls.source.index("struct V3SetupAssistantView"):cls.source.index("// V3_STATUS_TINT_V1")]

    def test_initial_status_is_unknown_not_all_missing(self):
        self.assertIn('@Published private(set) var setupSnapshotPhase = "checking"', self.store)
        self.assertIn('setupSnapshotPhase = "checking"\n        let outcome = await status.reloadAndWait()', self.store)
        self.assertIn('setupSnapshotPhase = "unavailable"', self.store)
        self.assertIn('setupSnapshotPhase = "observed"', self.store)
        self.assertLess(self.store.index('status.markSetupFactsObserved(revision: factRevision)'),
                        self.store.index('setupSnapshotPhase = "observed"'))

    def test_unobserved_snapshot_never_shows_still_needed(self):
        self.assertIn('if setup.setupSnapshotPhase != "observed" {', self.view)
        self.assertIn('} else if !setup.outstandingSetup(status: status).isEmpty {', self.view)
        self.assertIn('Existing setup could not be verified. No settings were reset.', self.view)
        self.assertIn('Checking existing setup. Nothing needs to be reconfigured yet.', self.view)
        self.assertIn('Button("Re-check Setup Status")', self.view)
        self.assertNotIn('removePersistentDomain', self.view)
        self.assertNotIn('clearPairingFile', self.view)

    def test_refresh_cannot_mutate_during_unverified_setup(self):
        self.assertIn('SCARLET_V176_REFRESH_UNKNOWN_BLOCK', self.store)
        self.assertIn('guard setupSnapshotPhase == "observed" else {', self.store)
        self.assertIn('test_refresh=blocked reason=status_unobserved', self.store)
        self.assertIn('} else if setup.setupSnapshotPhase != "observed" {', self.view)
        self.assertIn('Test Refresh is unavailable until existing setup status is verified.', self.view)

    def test_diagnostics_never_claim_wifi_or_account_success_when_unknown(self):
        self.assertIn('lines.append("Setup snapshot: " + setupSnapshotPhase)', self.store)
        self.assertIn('Pairing: unknown (status not observed)', self.store)
        self.assertIn('Account: unknown (status not observed)', self.store)
        self.assertIn('let wifiText = network.state == "complete" ? "available"', self.store)

if __name__=="__main__":
    unittest.main()
