"""R6P130: automatic renewal cannot compete with interactive account work."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
AUTO = (ROOT / "HostApp/ScarletAutomaticRenewal.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
CERT = (ROOT / "HostApp/ScarletCertificateXPCSupport.swift").read_text()
REC = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
WORKER = (ROOT / "integration/ScarletGuestCertificateAgent.swift.txt").read_text()

class AccountRefreshPriority(unittest.TestCase):
    def test_settings_owns_interactive_account_window(self):
        self.assertIn('setSettingsInteractionActive(raw == "설정")', HOST)
        self.assertIn('private var settingsInteractionActive = false', AUTO)
        guard = AUTO.split('private func refreshIfDue(origin:', 1)[1]
        self.assertLess(guard.index('guard !settingsInteractionActive'), guard.index('prefs.set(Date(), forKey: attemptKey)'))
        self.assertIn('pendingVerifiedAccountSwitch = true', AUTO)
        self.assertIn('if wasActive && !active && pendingVerifiedAccountSwitch', AUTO)
        self.assertIn('pendingVerifiedAccountSwitch ? "verified_account_switch" : "foreground"', AUTO)

    def test_certificate_request_reserves_id_before_suspending(self):
        request = CERT.split('private func performRequest(', 1)[1].split('func finished(', 1)[0]
        self.assertLess(request.index('requestID = id'), request.index('try await ScarletNativeAuthTransport.shared.prepare()'))
        self.assertLess(request.index('defer { requestID = nil; completion = nil }'), request.index('try await ScarletNativeAuthTransport.shared.prepare()'))

    def test_worker_cert_access_uses_same_team_lease_and_snapshots_before_release(self):
        self.assertEqual(WORKER.count("guard await ScarletTeamOperationGate.shared.claim()"), 2)
        self.assertEqual(WORKER.count("let archive = active.p12Data"), 2)
        self.assertEqual(WORKER.count("let password = active.password"), 2)
        self.assertEqual(WORKER.count('domain: "scarlet.certificate.team_operation_in_progress"'), 2)
        for endpoint in (WORKER.split("static func issue(", 1)[1].split("static func retrieve(", 1)[0],
                         WORKER.split("static func retrieve(", 1)[1].split("private static func report", 1)[0]):
            self.assertLess(endpoint.index("let archive = active.p12Data"),
                            endpoint.rindex("await ScarletTeamOperationGate.shared.release()"))
            self.assertLess(endpoint.rindex("await ScarletTeamOperationGate.shared.release()"),
                            endpoint.rindex("report(requestID, code: 0"))
    def test_background_renewal_and_busy_cooldown(self):
        self.assertEqual(AUTO.count("UIApplication.shared.applicationState == .background"), 2)
        self.assertIn("let previousAttempt = prefs.object(forKey: attemptKey) as? Date", AUTO)
        self.assertIn('reason == "team_operation_in_progress" || reason == "already_running"', AUTO)
        self.assertIn('if let previousAttempt { prefs.set(previousAttempt, forKey: attemptKey) }', AUTO)

    def test_exact_long_receipt_survives_privacy_filter(self):
        self.assertIn('"native_selected_team_refresh_returned_install_unverified"', REC)
        self.assertIn('if Self.fixedLongCategories.contains(source) { return source }', REC)
        self.assertIn('candidate.count > 54', REC)

if __name__ == "__main__":
    unittest.main()
