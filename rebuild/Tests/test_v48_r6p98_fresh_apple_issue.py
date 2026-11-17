"""P98: manual issue means Apple API issuance, not previous P95/P97 reuse."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
PANEL=(R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
XPC=(R/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
SIDE=(R/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
WIRE=(R/'rebuild/integration/wire_scarlet_auth.py').read_text()

class FreshAppleCertificateIssue(unittest.TestCase):
    def test_existing_user_button_calls_only_fresh_api(self):
        body=PANEL.split('private func requestNativeCertificate()',1)[1].split('private func retrieveSideInstallerStyleCertificate()',1)[0]
        self.assertIn('.issueFreshInstallCertificate(owner.teamID)',body)
        self.assertNotIn('.issueInstallCertificate(owner.teamID)',body)
        self.assertIn('result.0 && result.1 == "ready_issued_apple"',body)
        self.assertNotIn('"ready_existing_portal"',body)
        self.assertIn('case "selected_team_certificate_quota_reached":',body)
        self.assertIn('let source = "new_apple_portal"',body)
        self.assertIn('Apple에서 새 인증서를 발급받았습니다.',body)
        self.assertEqual(PANEL.count('Label("SideStore 인증서 받기"'),1)
    def test_fresh_request_has_independent_authenticated_xpc(self):
        self.assertIn('static func issueFreshInstallCertificate(_ teamID:',XPC)
        self.assertIn('teamOperation(teamID, issue: true, forceFresh: true)',XPC)
        self.assertIn('client.scarletIssueFreshInstallTeamCertificate(teamID, reply: callback)',XPC)
        self.assertIn('scarletIssueFreshInstallTeamCertificate:(NSString*)teamID',WIRE)
        self.assertIn('@selector(issueFreshInstallTeamCertificate:reply:)',WIRE)
        self.assertIn('@objc(issueFreshInstallTeamCertificate:reply:)',SIDE)
        self.assertIn('teamID: id, forceNew: true)',SIDE)
        self.assertIn('reply(status == "ready_issued_apple", status)',SIDE)
    def test_reuse_is_outside_force_fresh_and_direct_apple_call_remains(self):
        body=SIDE.split('static func issue(teamID: String, forceNew: Bool)',1)[1].split('extension ScarletGuestSignInAgent',1)[0]
        self.assertIn('if !forceNew {',body)
        self.assertIn('return "ready_existing_portal"',body)
        self.assertLess(body.index('if !forceNew {'),body.index('for remote in portal'))
        self.assertLess(body.index('} // Explicit new issuance'),body.index('DeveloperPortalProxy.shared.createCertificate('))
        self.assertIn('previouslyRegistered.contains(',body)
        self.assertIn('selected_team_certificate_new_issue_not_created',body)
        self.assertIn('selected_team_certificate_new_issue_unconfirmed',body)
        self.assertIn('.fetchCertificates(team: team)',body)
        self.assertNotIn('revokeCertificate(',body)
        self.assertNotIn('SecItemDelete(',body)
    def test_guest_host_signer_error_not_overwritten_by_refresh_readback(self):
        self.assertIn('if !nativeState.signingReady && certificateRecoveryStatus ==',PANEL)
        self.assertIn('호스트 재서명·업데이트가 필요합니다.',PANEL)
        self.assertIn('new_apple_p12_already_active_in_native_store',PANEL)

if __name__=='__main__': unittest.main()
