"""V20 contracts: anonymous guest-side UI telemetry survives LC app handoff.

The device V19 host JSONL contained recent_session_registered(count=1,2) but
no guest switcher panel/rotation events. This may be because the guest owns
a separate virtualized Application Support location, not because the panel
failed to appear. The host now replays an App Group trace on foreground.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
LEDGER=(ROOT/"HostApp/ScarletGuestSessionLedger.swift").read_text()
FULL=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
NATIVE=(ROOT/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
DIAG=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()

class SwitcherCrossSandboxTrace(unittest.TestCase):
    def test_guest_does_not_export_names_or_secret_values(self):
        self.assertIn('private static let switchTraceKey = "Scarlet.Guest.SwitcherTrace.V20"',LEDGER)
        self.assertIn('private static let switchTraceEvents: Set<String>', LEDGER)
        self.assertIn('guard switchTraceEvents.contains(event) else { return }', LEDGER)
        self.assertIn('let event: String', LEDGER)
        self.assertIn('let count: Int', LEDGER)
        self.assertIn('max(0, min(count, 8))', LEDGER)
        self.assertNotIn('guestName', LEDGER)
        self.assertNotIn('password', LEDGER.lower())
        self.assertNotIn('bundleID', LEDGER)
        self.assertIn('suffix(48)', LEDGER)
        self.assertNotIn('removePersistentDomain(', LEDGER)

    def test_guest_input_path_replays_into_host_journal(self):
        self.assertIn('static func replaySwitcherTraceToHostJournal()', LEDGER)
        self.assertIn('ScarletDiagnosticRecorder.shared.record(', LEDGER)
        self.assertIn('"guest_switcher", entry.event,', LEDGER)
        self.assertIn('"source": "guest_app_group"', LEDGER)
        self.assertIn('UserDefaults.standard.set(newest, forKey: switchTraceCursor)', LEDGER)
        self.assertEqual(HOST.count('ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()'),2)
        self.assertIn('func readRecent(maxLines: Int = 350)', DIAG)

    def test_fullscreen_guest_mount_panel_and_handoff_taps_visible(self):
        for s in ('"fullscreen_tab_mounted"', '"panel_opened"',
                  '"panel_closed"', '"switch_tapped_live"',
                  '"switch_tapped_cold"', '"switch_rejected"',
                  '"switch_submitted"', '"switch_submit_failed"',
                  '"rotation_relayout"'):
            self.assertIn(s,FULL)
            self.assertIn(s,LEDGER)
        self.assertIn('try await app.runApp()',HOST)
        self.assertIn('ScarletGuestSessionLedger.noteLaunch(',HOST)
        self.assertIn('ScarletGuestSessionLedger.recent()', FULL)
        self.assertIn('Scarlet.Guest.ActiveSwitcherSession.V19',LEDGER)

    def test_native_scene_switcher_taps_also_observed(self):
        for s in ('"native_panel_opened"','"native_switch_tapped"',
                  '"native_switch_rejected"','"native_switch_activated"'):
            self.assertIn(s,NATIVE)
            self.assertIn(s,LEDGER)

    def test_no_unrequested_glass_change(self):
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',FULL)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)',FULL)
        self.assertIn('@State private var isOpen = false',FULL)
        self.assertIn('@State private var isOpen = false',NATIVE)
        self.assertIn('let canRelaunch = containerExists != nil',FULL)

if __name__=="__main__":
    unittest.main()
