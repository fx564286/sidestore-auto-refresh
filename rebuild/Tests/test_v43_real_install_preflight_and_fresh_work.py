"""V43 iPhone install trace regression and one clean V43 work session.
Source-level checks; iOS installer success still requires a signed-device test.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
AGENT=(ROOT/'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
REFRESH=(ROOT/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
AUTH=(ROOT/'integration/ScarletGuestSignInAgent.swift.txt').read_text()
WIRE=(ROOT/'integration/wire_scarlet_auth.py').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
LEDGER=(ROOT/'HostApp/ScarletGuestSessionLedger.swift').read_text()
WORKFLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class V43Installer(unittest.TestCase):
    def test_reuses_original_refresh_team_recovery_without_creating_cert(self):
        self.assertIn('ScarletGuestSignInAgent\n                    .ensureActiveTeamForRefresh()',AGENT)
        self.assertIn('static func ensureActiveTeamForRefresh() async -> String',AUTH)
        self.assertIn('teamState == "ready" || teamState == "team_restored"',AGENT)
        self.assertIn('notify(teamState == "sidestore_team_mismatch"',AGENT)
        self.assertIn('ScarletGuestDeviceTransport.ensureReady()',AGENT)
        self.assertIn('private enum ScarletGuestDeviceTransport',REFRESH)
        self.assertIn('AppBootManager.shared.startMinimuxer(pairingFile: pairing)',REFRESH)
        self.assertNotIn('revokeCertificate(',AGENT)
        self.assertNotIn('requestCertificate(',AGENT)

    def test_works_through_original_appmanager_callback(self):
        self.assertIn('CertificateManager.shared.loadActiveCertificate()',AGENT)
        self.assertIn('AppManager.shared.install(.url(fileURL))',AGENT)
        self.assertIn('continuation.resume(with: result)',AGENT)
        self.assertIn('notify("installed")',AGENT)
        self.assertIn('name: Notification.Name("ScarletDeviceInstallCompleted")',AGENT)
        self.assertIn('selector:@selector(scarletInstallCompleted:)',WIRE)
        self.assertIn('handler.server finish:nil',WIRE)

    def test_stage_specific_redacted_error_without_private_data(self):
        self.assertIn('safeFailureReason(error, phase: "transport")',AGENT)
        self.assertIn('safeFailureReason(error, phase: "appmanager")',AGENT)
        self.assertIn('safeFailureReason(error, phase: "preflight")',AGENT)
        for name in ('minimuxer_not_started','team_unavailable','team_mismatch',
                     'pairing_invalid','network_unavailable','appmanager_error_code_'):
            self.assertIn(name, AGENT+HOST)
        self.assertIn('if let range = normalized.range(of: marker)',HOST)
        self.assertIn('let reason = knownReasons.contains(exactReason) || typedAppManagerCode',HOST)
        self.assertIn('"install_failed", status: "error"',HOST)
        self.assertIn('"stage": stage',HOST)
        self.assertIn('"installation_verified": "false"',HOST)
        self.assertNotIn('fields: ["description": nsError.localizedDescription]',HOST)
        self.assertIn('FileManager.default.copyItem(at: source, to: staged)',HOST)
        self.assertIn('defer { try? FileManager.default.removeItem(at: staged) }',HOST)

    def test_completion_does_not_falsely_claim_real_ios_install(self):
        self.assertIn('"appmanager_callback_completed"',HOST)
        self.assertIn('deviceInstallStatus = "설치 엔진 반환 · 실제 iPhone 설치 결과 확인 필요"',HOST)
        self.assertIn('"installation_verified": "false"',HOST)
        self.assertNotIn('install_operation_returned", status: "success"',HOST)

    def test_clean_v43_session_no_carryover_from_v40_v42(self):
        for key in ('ActiveSwitcherSession','WorkSessionID',
                    'HostReturnTicket','LaunchBootEpoch','DepartedTicket'):
            self.assertIn(f'Scarlet.Guest.{key}.V43',LEDGER)
            self.assertNotIn(f'private static let key = "Scarlet.Guest.ActiveSwitcherSession.V40"',LEDGER)
        self.assertIn('startFreshWorkSession()',LEDGER)
        self.assertIn('cold_host_new_session',LEDGER)
        self.assertIn('noteGuestDeparted(folder: String)',LEDGER)
        self.assertIn('verified_guest_departure_continued',LEDGER)

    def test_original_v40_iphone_geometry_and_switcher_unchanged(self):
        self.assertIn('try await app.runApp(multitask: false)',HOST)
        self.assertNotIn('ScarletResidentGuestSwitchController',HOST)
        self.assertNotIn('ScarletResidentGuestMode.V41',HOST)
        self.assertNotIn('MultitaskMode.virtualWindow',HOST)
        self.assertIn('fix/scarlet-v43-install-rootcause-20261110',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V43-UNSIGNED.ipa',WORKFLOW)

if __name__=='__main__':
    unittest.main()
