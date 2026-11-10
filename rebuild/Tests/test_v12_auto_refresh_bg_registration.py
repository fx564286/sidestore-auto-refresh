"""V12 native SideStore background refresh is wired, not an idle UI label."""
from pathlib import Path
import unittest
D=Path(__file__).resolve().parents[1]
ENGINE=(D/"HostApp/ScarletAutomaticRenewal.swift").read_text()
INTEGRATION=(D/"integration/apply_scarlet_host.py").read_text()
HOST=(D/"HostApp/ScarletIntegratedHostView.swift").read_text()
PANEL=(D/"HostApp/ScarletSigningReadinessPanel.swift").read_text()

class AutoRenewalContract(unittest.TestCase):
    def test_bg_registration_during_app_launch(self):
        self.assertIn('ScarletAutomaticRenewal.shared.registerAtLaunch()',INTEGRATION)
        self.assertIn('LiveContainerSwiftUI/App/AppDelegate.swift',INTEGRATION)
        self.assertIn('BGTaskSchedulerPermittedIdentifiers',INTEGRATION)
        self.assertIn('com.kdt.livecontainer.P8EZT3U5N4.refresh',INTEGRATION)
        self.assertIn('BGTaskScheduler.shared.register(',ENGINE)
        self.assertIn('BGTaskScheduler.shared.submit(request)',ENGINE)
        self.assertIn('task.expirationHandler' if False else 'bg.expirationHandler', ENGINE)
        self.assertIn('ScarletAutomaticRenewal.swift',INTEGRATION)

    def test_invoke_pinned_sidestore_on_due_and_retry(self):
        self.assertIn('ScarletNativeRefreshExecutor.execute()',ENGINE)
        self.assertIn('ScarletSigningReadiness.inspect()',ENGINE)
        self.assertIn('storedAuthenticated()',ENGINE)
        self.assertIn('2 * 3600 : 6 * 3600',ENGINE)
        self.assertIn('automatic_request_failed',ENGINE)
        self.assertIn('installation_verified": "false"',ENGINE)
        self.assertNotIn('revokeCertificate(',ENGINE)
        self.assertNotIn('removeItem(',ENGINE)
        self.assertNotIn('installedAndVerified',ENGINE)

    def test_foreground_catchup_and_honest_display(self):
        self.assertEqual(HOST.count('ScarletAutomaticRenewal.shared.foregroundCatchUp()'),2)
        self.assertIn('LabeledContent("자동 갱신",',PANEL)
        self.assertIn('iOS 예약 · 대기 중',PANEL)
        self.assertIn('lastRefreshAttemptState',PANEL)
        self.assertIn('Scarlet.Refresh.LastAttemptOutcome',PANEL)

if __name__=="__main__": unittest.main()
