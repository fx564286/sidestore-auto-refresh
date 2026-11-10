"""V19 regression: installed apps are NOT guest switcher tabs.

The iPhone app diagnostic SourceCommit a5c59b1bf2af reports 3 installed
guests and a 3-entry V14 lifetime ledger. A/B switching must survive
host -> guest process handoff, without importing historic installed rows.

This source contract is not a substitute for real iPhone UI testing.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()
PANEL = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
NATIVE = (ROOT / "HostApp/ScarletGuestSwitcherOverlay.swift").read_text()

class V19SessionSwitcher(unittest.TestCase):
    def test_old_installed_and_lifetime_history_is_not_loaded(self):
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V43"', LEDGER)
        self.assertIn('Legacy key: Scarlet.Guest.ActiveSwitcherSession.V19', LEDGER)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.ActiveSwitcherSession.V19")', LEDGER)
        self.assertIn('Legacy key: Scarlet.Guest.RecentSessions.V14', LEDGER)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.RecentSessions.V14")', LEDGER)
        self.assertIn('private static let maxItems = 8', LEDGER)
        self.assertNotIn('inactivityTimeout:', LEDGER)
        self.assertIn('static func prepareForHostAppearance()', LEDGER)
        self.assertIn('Scarlet.Guest.HostReturnTicket.V43', LEDGER)
        self.assertIn('legitimateGuest', LEDGER)
        self.assertIn('return Array(raw.filter {', LEDGER)

    def test_a_home_b_retained_without_ever_installed_fallback(self):
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(', HOST)
        self.assertLess(HOST.index('ScarletGuestSessionLedger.noteLaunch('),
                        HOST.index('try await app.runApp()'))
        self.assertIn('recent().filter { $0.folder != folder }', LEDGER)
        self.assertIn('let recentFolders = Set(recent.map(\\.folder))', PANEL)
        self.assertIn('guard isCurrent || activeScene || recentFolders.contains(folder) else', PANEL)
        self.assertIn('for entry in history', NATIVE)
        self.assertNotIn('lastLaunched != nil && !isCurrent', PANEL)

    def test_shared_data_uuid_is_not_app_identity(self):
        self.assertIn('let isCurrent = hasRuntimeIdentity && matchesRuntime', PANEL)
        self.assertNotIn(': (folder == selected || bundleID == selected)', PANEL)
        self.assertIn('let matchesRuntime = folder == runtimeID || bundleID == runtimeID ||', PANEL)
        self.assertNotIn('containerExists == selectedContainer', PANEL)
        self.assertIn('guard !found.contains(folder)', PANEL)
        self.assertIn('!display.isEmpty', PANEL)
        self.assertIn('(meta["isHidden"] as? Bool) != true', PANEL)
        self.assertIn('(meta["isLocked"] as? Bool) != true', PANEL)

    def test_strict_session_model_examples(self):
        # V23 no longer merges a prior 30-minute ledger into a fresh host.
        # Reference simulation; iPhone runtime still requires device tests.
        installed = {"A.app", "B.app", "C.app", "D.app"}
        previous_session = ["B.app", "C.app"]
        session = []  # fresh host entry clears V23 only
        session = ["A.app"] + [x for x in session if x != "A.app"]
        self.assertEqual(set(session) & installed, {"A.app"})
        self.assertEqual(set(session) & set(previous_session), set())
        # Explicit guest->Scarlet app list return retains the same session.
        session = ["B.app"] + [x for x in session if x != "B.app"]
        self.assertEqual(set(session) & installed, {"A.app", "B.app"})
        # A host opened independently starts another session even within 30m.
        session = []
        self.assertEqual(set(session) & installed, set())

    def test_glass_is_unchanged_by_switcher_filter(self):
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)', PANEL)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)', PANEL)

if __name__ == "__main__":
    unittest.main()
