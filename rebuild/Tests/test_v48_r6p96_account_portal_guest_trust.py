"""P96 source contract: serial-verified account reuse and separate host signer trust."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
UI=(ROOT/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
SIDE=(ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
HOST=(ROOT/'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()

class AccountPortalTrustContract(unittest.TestCase):
    def test_button_runs_explicit_portal_issuing_not_quick_local_ready(self):
        body=UI.split('private func requestNativeCertificate()',1)[1].split('private func retrieveSideInstallerStyleCertificate()',1)[0]
        self.assertIn('issueFreshInstallCertificate(owner.teamID)',body)
        self.assertNotIn('ensureSelectedTeamCertificate(owner.teamID)',body)
        self.assertIn('native_account_issue_result',body)
        self.assertIn('"ready_issued_apple"',body)
        self.assertNotIn('"existing_portal"',body)

    def test_explicit_issue_checks_apple_portal_serial_and_owner(self):
        body=SIDE.split('static func issue(teamID: String)',1)[1].split('extension ScarletGuestSignInAgent',1)[0]
        self.assertIn('let owner = await activeOwnership()',body)
        self.assertIn('DeveloperPortalProxy.shared.fetchCertificates(team: team)',body)
        self.assertIn('$0.serialNumber.caseInsensitiveCompare(current.serialNumber)',body)
        self.assertIn('return "ready_existing_portal"',body)
        self.assertIn('DeveloperPortalProxy.shared.createCertificate(',body)
        self.assertIn('"selected_account_owner_changed"',body)
        self.assertGreater(body.index('return await prepare(teamID: teamID)'), body.index('let portal = try await DeveloperPortalProxy.shared.fetchCertificates(team: team)'))
        self.assertNotIn('SecItemDelete(',body)

    def test_guest_signer_requires_installed_profile_x509_match(self):
        body=UI.split('private func importExportedP12()',1)[1].split('var body: some View',1)[0]
        self.assertIn('ScarletHostProvisioningSigner.check(',body)
        self.assertIn('trust != .matched',body)
        self.assertIn('"account_p12_guest_signer_blocked"',body)
        self.assertIn('"candidate_not_in_host_profile"',HOST)
        self.assertIn('kernel postcheck',body)
        self.assertIn('guard !isImportingSelectedTeamP12 else { return false }',body)
        self.assertIn('await renewHostWithImportedSelectedCertificate(',body)
        self.assertIn('ScarletGuestSignerRecovery.trialExistingSideStoreCertificate(',body)

    def test_dont_conflate_managed_apps_with_cert_validity(self):
        self.assertIn('"no_managed_apps_for_selected_team"',
            (ROOT/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text())
        self.assertIn('"sidestore_managed_apps_inspected"',UI)

if __name__ == '__main__': unittest.main()
