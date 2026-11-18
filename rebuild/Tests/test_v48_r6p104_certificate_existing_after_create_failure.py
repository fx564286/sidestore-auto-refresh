"""P104 contract: Apple create is still attempted; safe same-owner rescue only afterward."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
SIDE=(ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
HOST=(ROOT/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
UI=(ROOT/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()

class AppleIssueExistingOwnerRecovery(unittest.TestCase):
    def test_fresh_call_survives_and_does_not_preempt_with_reuse(self):
        body=SIDE.split('static func issue(teamID: String, forceNew: Bool)',1)[1].split('extension ScarletGuestSignInAgent',1)[0]
        issued=body.index('newlyIssued = try await DeveloperPortalProxy.shared.createCertificate(')
        fallback=body.index('ready_existing_after_apple_issue_failed')
        self.assertLess(issued,fallback)
        self.assertIn('if forceNew,',body[issued:fallback])
        self.assertIn('portal.contains(where:',body[issued:fallback])
        self.assertIn('existing.x509.expiryDate > Date()',body[issued:fallback])
        self.assertIn('for: teamID, appleID: owner.appleID',body[issued:fallback])
        self.assertIn('stillOwner.appleID == owner.appleID',body[issued:fallback])
        self.assertIn('stillOwner.teamID == owner.teamID',body[issued:fallback])
        self.assertIn('await prepare(teamID: teamID) == "ready"',body[issued:fallback])
        self.assertIn('return portalFailure(error, stage: "create", reason: fallback)',body[fallback:])
        self.assertNotIn('revokeCertificate(',body)
        self.assertEqual(body.count('DeveloperPortalProxy.shared.createCertificate('),1)

    def test_native_protocol_and_ui_accept_only_labeled_recovery(self):
        self.assertIn('status == "ready_existing_after_apple_issue_failed", status)',SIDE)
        self.assertIn('"ready_existing_after_apple_issue_failed"',HOST)
        body=UI.split('private func requestNativeCertificate()',1)[1].split('private func retrieveSideInstallerStyleCertificate()',1)[0]
        self.assertIn('.issueFreshInstallCertificate(owner.teamID)',body)
        self.assertIn('let issuedNew = result.0 && result.1 == "ready_issued_apple"',body)
        self.assertIn('let reusedExisting = result.0 &&',body)
        self.assertIn('guard issuedNew || reusedExisting else',body)
        self.assertIn('existing_apple_portal_after_issue_failed',body)
        self.assertIn('fresh_issue_failed_existing_portal_cert_recovered',body)
        self.assertIn('새 인증서 발급에 실패했지만',body)
        self.assertNotIn('이 계정의 인증서로 호스트를 대신',body)

    def test_built_in_refresh_and_original_host_signer_remain_untouched(self):
        # The new fix must not spoof SideStore managed apps or install success.
        refresh=(ROOT/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
        self.assertIn('guard nativeState.canRefreshSelectedTeam else',refresh)
        self.assertIn('installation_verified": "false"',refresh)
        self.assertIn('ScarletHostProvisioningSigner.check(',UI)
        self.assertIn('ScarletGuestSignerRecovery.trialExistingSideStoreCertificate(',UI)

if __name__=='__main__': unittest.main()
