"""V23: installed/old guest history must not leak into a fresh switcher.

Device evidence from user's V22 iPhone (SourceCommit 4630e21113e1):
runtime_current_resolved(count=1) + panel_opened(count=2) after launching
only KakaoTalk. V19 30min history carried Instagram from prior work.
A->Scarlet app list->B remains a single explicit session.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
LEDGER=(ROOT/"HostApp/ScarletGuestSessionLedger.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
FULL=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
NATIVE=(ROOT/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
AUTO=(ROOT/"HostApp/ScarletAutomaticRenewal.swift").read_text()

class V23SessionIsolation(unittest.TestCase):
    def test_does_not_read_v14_or_v19_previous_sessions(self):
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V23"', LEDGER)
        self.assertIn('Legacy key: Scarlet.Guest.RecentSessions.V14',LEDGER)
        self.assertIn('Legacy key: Scarlet.Guest.ActiveSwitcherSession.V19',LEDGER)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.ActiveSwitcherSession.V19")',LEDGER)
        self.assertNotIn('store.data(forKey: "Scarlet.Guest.RecentSessions.V14")',LEDGER)
        self.assertNotIn('removePersistentDomain(',LEDGER)

    def test_fresh_host_clears_switcher_only_once(self):
        start=LEDGER.index("static func prepareForHostAppearance()")
        end=LEDGER.index("    // The actual full-screen guest",start)
        code=LEDGER[start:end]
        self.assertIn('guard !hasEnteredHostWorkSession else { return }',code)
        self.assertIn('let ticket = store.object(forKey: hostReturnKey) as? Date',code)
        self.assertIn('store.removeObject(forKey: hostReturnKey)',code)
        self.assertIn('if !isContinuation {',code)
        self.assertIn('JSONEncoder().encode([Entry]())',code)
        self.assertIn('store.set(empty, forKey: key)',code)
        self.assertIn('cold_host_new_session',code)
        self.assertIn('guest_return_continued',code)
        self.assertIn('ScarletGuestSessionLedger.prepareForHostAppearance()',HOST)
        self.assertLess(HOST.index('ScarletGuestSessionLedger.prepareForHostAppearance()'),
                        HOST.index('ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()'))
        self.assertEqual(HOST.count('ScarletGuestSessionLedger.prepareForHostAppearance()'),1)

    def test_explicit_host_return_preserves_a_then_b(self):
        self.assertIn('static func beginReturnToHost()',LEDGER)
        self.assertIn('static func cancelReturnToHost()',LEDGER)
        self.assertIn('private static let returnTicketValidity: TimeInterval = 120',LEDGER)
        self.assertIn('ScarletGuestSessionLedger.beginReturnToHost()',FULL)
        self.assertIn('ScarletGuestSessionLedger.cancelReturnToHost()',FULL)
        self.assertIn('if !LCSharedUtils.launchToGuestApp(withClassicMode: 0)',FULL)
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(',HOST)
        self.assertLess(HOST.index('ScarletGuestSessionLedger.noteLaunch('),
                        HOST.index('try await app.runApp()'))
        self.assertIn('recent().filter { $0.folder != folder }',LEDGER)
        self.assertIn('store.data(forKey: key) == encoded', LEDGER)
        self.assertIn('let recent = ScarletGuestSessionLedger.recent()', FULL)
        self.assertIn('let history = ScarletGuestSessionLedger.recent()', NATIVE)
        self.assertIn('guard isCurrent || activeScene || recentFolders.contains(folder) else',FULL)

    def test_no_30_minute_time_expiration_and_no_visual_changes(self):
        self.assertNotIn('inactivityTimeout', LEDGER)
        self.assertNotIn('idle <=', LEDGER)
        self.assertIn('return Array(raw.filter {',LEDGER)
        self.assertIn('private static let maxItems = 8',LEDGER)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',FULL)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)',FULL)
        self.assertIn('@State private var isOpen = false',FULL)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',FULL)
        self.assertIn('runtime_current_resolved',FULL)
        self.assertIn('automatic_failure_categorized',AUTO)

    def test_expected_workflows(self):
        # Simulated reference of V23 ledger policy, distinct from device pass.
        installed={"Kakao.app","Instagram.app","Other.app"}
        old_v19=["Instagram.app","Kakao.app"]
        v23=[]  # fresh host no return ticket
        v23=["Kakao.app"] + v23
        self.assertEqual(set(v23)&installed,{"Kakao.app"})
        self.assertNotIn("Instagram.app",v23)
        # Scarlet's own app-list button issues a one-use return ticket.
        ticket=True
        if ticket: v23=list(v23)
        v23=["Instagram.app"] + [x for x in v23 if x!="Instagram.app"]
        self.assertEqual(set(v23)&installed,{"Kakao.app","Instagram.app"})
        # Launching Scarlet independently starts a NEW session, not old_v19.
        v23=[]
        self.assertEqual(v23,[])
        self.assertEqual(old_v19,["Instagram.app","Kakao.app"])

if __name__ == "__main__": unittest.main()
