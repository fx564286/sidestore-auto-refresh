"""P68: signed iPhone logged team_mismatch on account B after successful 2FA.
These static proofs do not replace signed-device installation verification.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
VAULT=(ROOT/'integration/ScarletGuestSavedAccounts.swift.txt').read_text()
INSTALL=(ROOT/'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
REFRESH=(ROOT/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
WIRE=(ROOT/'integration/wire_scarlet_auth.py').read_text()
SUPPORT=(ROOT/'HostApp/ScarletAuthXPCSupport.swift').read_text()
LOGIN=(ROOT/'HostApp/ScarletAppleIDLoginSheet.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
AUTO=(ROOT/'HostApp/ScarletAutomaticRenewal.swift').read_text()

class TeamAandB(unittest.TestCase):
    def test_user_selects_install_team_before_ipa_picker(self):
        self.assertIn('ScarletInstallTeamPicker',LOGIN)
        self.assertIn('SCARLET_INSTALL_TEAM_PICKER',LOGIN)
        self.assertIn('SCARLET_SELECT_INSTALL_TEAM',LOGIN)
        self.assertIn('SCARLET_ISSUE_SELECTED_TEAM_CERT',LOGIN)
        self.assertIn('showInstallTeamPicker = true',HOST)
        self.assertIn('selectedInstallTeamID = teamID',HOST)
        self.assertIn('teamID: selectedTeamID',HOST)
        self.assertIn('ScarletNativeSavedAccounts.activate(row.id)',LOGIN)
        self.assertIn('.prepareInstallTeam(row.teamID)',LOGIN)
    def test_worker_receives_exact_selected_team_not_signed_host_team(self):
        self.assertIn('expectedTeamID',WIRE)
        self.assertIn('expectedTeamID',INSTALL)
        self.assertIn('identifier: "scarlet.install.ipa." + teamID',WIRE)
        self.assertIn('[identifier hasPrefix:@"scarlet.install.ipa."]',WIRE)
        self.assertIn('ScarletInstallTeamAuthority.prepare(',INSTALL)
        self.assertNotIn('.ensureActiveTeamForRefresh()',INSTALL)
        self.assertIn('AppManager.shared.install(.url(fileURL))',INSTALL)
        self.assertIn('P8EZT3U5N4', (ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text())
    def test_account_and_certificate_are_verified_per_team(self):
        self.assertIn('let teamID: String',VAULT)
        self.assertIn('let certificateReady: Bool',VAULT)
        self.assertIn('ScarletInstallTeamAuthority.matchingCertificate',VAULT)
        self.assertIn('certificateBelongsToTeam',VAULT)
        self.assertIn('Organizational Unit=',VAULT)
        self.assertIn('getAllLocalCertificates()',VAULT)
        self.assertIn('cert.x509.expiryDate > Date()',VAULT)
        self.assertIn('manager.setActiveCertificate(cert)',VAULT)
        self.assertIn('certificateBelongsToTeam(active.certificate, teamID: teamID)',VAULT)
        for forbidden in ('revokeCertificate(', 'deleteCertificate(',
                          'clearActiveCertificate()', 'AuthManager.shared.signOut()'):
            self.assertNotIn(forbidden,VAULT)
    def test_selected_team_certificate_issuance_is_explicit(self):
        self.assertIn('client.scarletIssueInstallTeamCertificate',SUPPORT)
        self.assertIn('issueInstallCertificate(teamID)',LOGIN)
        self.assertIn('CertificateProvisioningFlow(handler: nil)',VAULT)
        self.assertIn('ScarletInstallTeamAuthority.issue(teamID:',VAULT)
        self.assertNotIn('certificateData',LOGIN)
    def test_refresh_scoped_to_native_installedapp_team_not_other_account_host(self):
        self.assertIn('$0.team?.identifier == selectedTeam.identifier',REFRESH)
        self.assertIn('let managedHost = targets.first',REFRESH)
        self.assertIn('if let managedHost {',REFRESH)
        self.assertIn('native_selected_team_refresh_returned_install_unverified',REFRESH)
        self.assertIn('no_managed_apps_for_selected_team',REFRESH)
        self.assertIn('native_selected_team_refresh_returned_install_unverified',SUPPORT)
        self.assertIn('no_managed_apps_for_selected_team',AUTO)
        self.assertNotIn('reply(true, "installed")',REFRESH)
    def test_install_team_switch_is_not_secret_logging_or_host_resigning(self):
        self.assertNotIn('fields: ["teamID":',HOST)
        self.assertNotIn('UserDefaults.standard.set(slot.xcodeToken',VAULT)
        self.assertNotIn('UserDefaults.standard.set(slot.password',VAULT)
        self.assertIn('readiness.canRequestNativeRefresh',HOST)

if __name__=='__main__': unittest.main()
