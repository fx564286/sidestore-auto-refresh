"""V39 source regressions for the reported 18:56 KST on-device session."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
A=(ROOT/'HostApp/ScarletAutomaticRenewal.swift').read_text()
D=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
H=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
L=(ROOT/'HostApp/ScarletGuestSessionLedger.swift').read_text()
W=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class V39TrueLogSemantics(unittest.TestCase):
    def test_backlog_not_counted_as_current_guest_events(self):
        self.assertIn('let fresh = entries.filter { entry in', L)
        self.assertIn('entry.createdAt.map { $0 >= processStart } ?? false',L)
        self.assertIn('"count": String(fresh.count)',L)
        self.assertIn('"source": "current_process_only"',L)
        self.assertNotIn('"count": String(entries.count)',L)

    def test_actual_scene_orientation_is_logged_not_redacted(self):
        self.assertIn('window?.windowScene?.interfaceOrientation ?? .unknown',H)
        for text in ('"portrait"','"portrait_upside_down"',
                     '"landscape_left"','"landscape_right"','"unknown"'):
            self.assertIn(text,H)
        self.assertNotIn('String(describing: UIDevice.current.orientation)',H)
        self.assertIn('signature != lastLayoutSignature',H)
        self.assertIn('lastLayoutSignature = signature',H)
        self.assertIn('"safe_top_pt": String(top)',H)
        self.assertIn('"safe_bottom_pt": String(bottom)',H)

    def test_duplicate_foreground_retry_deferral_is_collapsed(self):
        self.assertIn('lastDeferredReportAt: Date?',A)
        self.assertIn('now.timeIntervalSince($0) >= 30',A)
        self.assertIn('"retry_minutes": String(remainingMinutes)',A)
        self.assertIn('"retry_minutes"',D)
        self.assertIn('lastCheckWasDeferred = true',A)
        self.assertIn('"installation_verified": "false"',A)
        self.assertIn('prefs.set(Date(), forKey: attemptKey)',A)
        self.assertNotIn('installation_verified": "true"',A)

    def test_v39_release_does_not_reenable_virtual_windows(self):
        self.assertIn('fix/scarlet-v39-log-truth-20261110',W)
        self.assertIn('Scarlet-Crystal-V39-UNSIGNED.ipa',W)
        self.assertIn('try await app.runApp(multitask: false)',H)
        self.assertNotIn('MultitaskMode.virtualWindow',H)

if __name__ == '__main__':
    unittest.main()
