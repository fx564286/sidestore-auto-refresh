"""V19 regression: installed apps are NOT guest switcher tabs.

The iPhone app diagnostic SourceCommit a5c59b1bf2af reports 3 installed
guests and a 3-entry V14 lifetime ledger. A/B switching must survive
host -> guest process handoff, without importing historic installed rows.

This source contract is not a substitute for real iPhone UI testing.
"""
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
LEDGER = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()
PANEL = (ROOT / "HostApp/ScarletFullscreenGuestTab.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
NATIVE = (ROOT / "HostApp/ScarletGuestSwitcherOverlay.swift").read_text()

class V19SessionSwitcher(unittest.TestCase):
    def test_old_installed_and_lifetime_history_is_not_loaded(self):
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V19"', LEDGER)
        self.assertIn('Legacy key: Scarlet.Guest.RecentSessions.V14', LEDGER)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.RecentSessions.V14")', LEDGER)
        self.assertIn('private static let maxItems = 8', LEDGER)
        self.assertIn('private static let inactivityTimeout: TimeInterval = 30 * 60', LEDGER)
        self.assertIn('let idle = Date().timeIntervalSince(newest)', LEDGER)
        self.assertIn('idle <= inactivityTimeout', LEDGER)
        self.assertIn('return valid', LEDGER)

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
        self.assertIn('let isCurrent = folder == selected || bundleID == selected ||', PANEL)
        self.assertNotIn('containerExists == selectedContainer', PANEL)
        self.assertIn('guard !found.contains(folder)', PANEL)
        self.assertIn('!display.isEmpty', PANEL)
        self.assertIn('(meta["isHidden"] as? Bool) != true', PANEL)
        self.assertIn('(meta["isLocked"] as? Bool) != true', PANEL)

    def test_strict_session_model_examples(self):
        # Reference for the Swift V19 policy; direct runtime validation
        # remains a separate acceptance criterion.
        now = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
        def visible(installed, history, current, live, max_age=timedelta(minutes=30)):
            valid = [name for name, when in history if name in installed and
                     name.endswith(".app") and now - when <= max_age]
            return {x for x in installed if x == current or x in live or x in valid}
        installed = {"A.app", "B.app", "C.app", "D.app"}
        self.assertEqual(visible(installed, [], "A.app", set()), {"A.app"})
        history = [("A.app", now-timedelta(minutes=3)),
                   ("B.app", now-timedelta(minutes=1))]
        self.assertEqual(visible(installed, history, "B.app", set()),
                         {"A.app", "B.app"})
        old = history + [("C.app", now-timedelta(days=1))]
        self.assertEqual(visible(installed, old, "B.app", set()),
                         {"A.app", "B.app"})
        self.assertEqual(visible(installed, [], "B.app", {"A.app"}),
                         {"A.app", "B.app"})

    def test_glass_is_unchanged_by_switcher_filter(self):
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)', PANEL)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)', PANEL)

if __name__ == "__main__":
    unittest.main()
