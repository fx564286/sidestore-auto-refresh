"""P95: explicit UI issuance must use the account-owned Apple portal worker."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PANEL=(ROOT/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
SIDE=(ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
XPC=(ROOT/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()

class NativeInAppAppleIssue(unittest.TestCase):
    def test_existing_button_uses_selected_owner_team_issuer_first(self):
        body=PANEL.split('private func requestNativeCertificate()',1)[1].split('private func retrieveSideInstallerStyleCertificate()',1)[0]
        self.assertIn('before.accounts.filter({ $0.active }).count == 1',body)
        self.assertIn('ensureSelectedTeamCertificate(owner.teamID)',body)
        self.assertIn('after.accounts.filter({ $0.active }).count == 1',body)
        self.assertIn('$0.id == owner.id && $0.teamID == owner.teamID',body)
        self.assertIn('retrieveSideStoreCertificate()',body)
        self.assertNotIn('ScarletNativeCertificateTransport.shared.obtain()',body)
        self.assertNotIn('retrieveSideInstallerStyleCertificate()',body)
    def test_receipt_distinguishes_actual_new_apple_issue_from_reuse(self):
        self.assertIn('native_account_issue_result',PANEL)
        self.assertIn('"ready_issued_apple"',PANEL)
        self.assertIn('"new_apple_portal" : "existing_portal"',PANEL)
        self.assertIn('selected_team_certificate_quota_reached',PANEL)
        self.assertIn('기존 유효 인증서를 사용했습니다. 신규 발급은 없으며',PANEL)
        self.assertIn('Apple에서 새 인증서를 발급받았습니다.',PANEL)
    def test_original_native_apple_issue_is_real_and_preserves_other_certs(self):
        self.assertIn('DeveloperPortalProxy.shared.createCertificate(',SIDE)
        self.assertIn('CertificateManager.shared',SIDE)
        self.assertIn('manager.setActiveCertificate(newlyIssued)',SIDE)
        self.assertIn('return "ready_issued_apple"',SIDE)
        self.assertIn('let issued = await issueInstallCertificate(teamID)',XPC)
        self.assertIn('let confirmed = await prepareInstallTeam(teamID)',XPC)
        self.assertNotIn('SecItemDelete(',PANEL)

if __name__=='__main__': unittest.main()
