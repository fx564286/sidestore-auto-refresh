"""V21 regression: distinguish injection failure from failed SwiftUI overlay.

V20 iPhone report (SourceCommit f17db18e6b29) has 0 guest_switcher
events, but A/B ledger stores successfully; host-only logs do not prove
that a guest-side UIKit hook ever ran. No user-identifying data in trace.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
INTEGRATION=(ROOT/"integration/apply_scarlet_host.py").read_text()
LEDGER=(ROOT/"HostApp/ScarletGuestSessionLedger.swift").read_text()
DIAG=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
FULL=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()

class GuestHookBridgeV21(unittest.TestCase):
    def test_objc_guest_hook_records_before_swift_class_lookup(self):
        self.assertIn('static void ScarletGuestHookTrace(NSString *event)', INTEGRATION)
        self.assertIn('ScarletGuestHookTrace(@\\\"hook_entered\\\")', INTEGRATION)
        self.assertIn('ScarletGuestHookTrace(@\\\"framework_missing\\\")', INTEGRATION)
        self.assertIn('ScarletGuestHookTrace(@\\\"framework_loaded\\\")', INTEGRATION)
        self.assertIn('ScarletGuestHookTrace(@\\\"provider_missing\\\")', INTEGRATION)
        self.assertIn('ScarletGuestHookTrace(@\\\"provider_ready\\\")', INTEGRATION)
        self.assertIn('NSUserDefaults.lcSharedDefaults', INTEGRATION)
        self.assertIn('Scarlet.Guest.SwitcherTrace.V20', INTEGRATION)
        self.assertIn('NSJSONSerialization dataWithJSONObject:entries', INTEGRATION)
        self.assertIn('entries.count > 48', INTEGRATION)
        self.assertLess(INTEGRATION.index('ScarletGuestHookTrace(@\\\"hook_entered\\\")'),
                        INTEGRATION.index('NSClassFromString(@\\\"ScarletFullscreenGuestTabInstaller\\\")'))
        self.assertNotIn('guestTitle', INTEGRATION.split('static void ScarletGuestHookTrace',1)[1].split('guest_hook_source = guest_hook_source.replace',1)[0])

    def test_host_journal_always_imports_before_share_and_display(self):
        self.assertIn('trace_bridge_empty', LEDGER)
        self.assertIn('trace_bridge_readable', LEDGER)
        self.assertIn('hook_entered', LEDGER)
        self.assertIn('framework_missing', LEDGER)
        self.assertIn('provider_missing', LEDGER)
        self.assertIn('private static var traceReaderReported = false', LEDGER)
        self.assertIn('ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()', DIAG)
        self.assertLess(DIAG.index('ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()'),
                        DIAG.index('ScarletDiagnosticRecorder.shared.record("diagnostics", "viewer_opened")'))
        self.assertEqual(HOST.count('ScarletGuestSessionLedger.replaySwitcherTraceToHostJournal()'),2)

    def test_unrelated_state_preserved(self):
        self.assertIn('Scarlet.Guest.ActiveSwitcherSession.V19', LEDGER)
        self.assertIn('private static let maxItems = 8', LEDGER)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)', FULL)
        self.assertNotIn('Color(uiColor: .systemBackground).opacity(0.88)', FULL)
        self.assertIn('guard target.canSwitch || target.canRelaunch else',FULL)
        self.assertNotIn('removePersistentDomain(', LEDGER)

if __name__=="__main__":
    unittest.main()
