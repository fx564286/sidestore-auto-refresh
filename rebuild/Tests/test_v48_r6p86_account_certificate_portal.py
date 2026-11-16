"""P86 user-triggered multi-account Apple portal certificate preflight.
These source contracts do not establish a live Apple portal transaction.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
VAULT=(R/'integration/ScarletGuestSavedAccounts.swift.txt').read_text()
SETTINGS=(R/'integration/apply_scarlet_host.py').read_text()
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
XPC=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
UPSTREAM=Path('/tmp/scarlet-sidestore-pinned/SideStore/Core/Auth/Flows/CertificateProvisioningFlow.swift')
class P86CertificatePortal(unittest.TestCase):
 def test_apple_issued_when_current_team_has_no_signable_certificate(self):
  part=VAULT.split('static func issue(teamID:',1)[1].split('extension ScarletGuestSignInAgent',1)[0]
  self.assertIn('matchingCertificate(for: teamID)',part)
  self.assertIn('DeveloperPortalProxy.shared.fetchCertificates(team: team)',part)
  self.assertIn('manager.getSignableCertificate(',part)
  self.assertIn('certificateBelongsToTeam(signable, teamID: teamID)',part)
  self.assertIn('DeveloperPortalProxy.shared.createCertificate(',part)
  self.assertIn('manager.setActiveCertificate(newlyIssued)',part)
  self.assertIn('await prepare(teamID: teamID) == "ready"',part)
  self.assertIn('selected_team_certificate_quota_reached',part)
  self.assertNotIn('CertificateProvisioningFlow(handler: nil)',part)
  for unsafe in ('revokeCertificate(', 'deleteCertificate(',
                 'clearActiveCertificate()', 'setActiveCertificate(nil)',
                 'signOut()', 'removeItem('):
   self.assertNotIn(unsafe,part)
 def test_xcode_ios_deployment_availability_for_embedded_settings_helper(self):
  # Xcode27.2 CI run 43858961897: LCSettingsView has an iOS<17 deployment
  # floor; helper directly references an iOS17-only native transport.
  self.assertIn('@available(iOS 17.0, *)\n    @MainActor\n    private func scarletEnsureCertificateForActiveAccount() async',SETTINGS)
  self.assertIn('if #available(iOS 17.0, *) {',SETTINGS)
 def test_user_login_switch_triggers_one_native_certificate_preflight(self):
  self.assertIn('private func scarletEnsureCertificateForActiveAccount() async',SETTINGS)
  self.assertIn('guard !scarletCertificateProvisionInFlight else { return }',SETTINGS)
  self.assertIn('await scarletEnsureCertificateForActiveAccount()',SETTINGS)
  self.assertIn('ScarletGuestAuthVerified',SETTINGS)
  self.assertIn('ensureSelectedTeamCertificate(teamID)',SETTINGS)
  self.assertIn('account_certificate_preflight_started',SETTINGS)
  self.assertIn('account_certificate_team_readback',SETTINGS)
  self.assertIn('readback.accounts.contains(where:',SETTINGS)
  self.assertNotIn('revokeCertificate(',SETTINGS)
 def test_ipa_taps_only_issue_for_selected_account_no_duplicate_picker(self):
  action=HOST.split('case .serviceInstallIPA:',1)[1].split('case .localOpenEmbeddedSideStore,',1)[0]
  self.assertIn('.ensureSelectedTeamCertificate(account.teamID)',action)
  self.assertIn('install_selected_team_certificate_result',action)
  self.assertIn('selectedInstallTeamID = account.teamID',action)
  self.assertIn('showGuestFilePicker = true',action)
  self.assertNotIn('ScarletInstallTeamPicker',action)
  self.assertNotIn('ScarletNativeSavedAccounts.activate(',action)
 def test_native_apple_result_and_keychain_ready_codes_not_silently_accepted(self):
  self.assertIn('selected_team_certificate_quota_reached',XPC)
  self.assertIn('selected_team_certificate_storage_failed',XPC)
  self.assertIn('ready_existing_portal',XPC)
  self.assertIn('ready_issued_apple',XPC)
  self.assertIn('let confirmed = await prepareInstallTeam(teamID)',XPC)
  self.assertIn('selected_team_certificate_readback_failed',XPC)
  self.assertIn('let success = reason == "ready" ||',XPC)
 def test_real_apple_issuance_upstream_matching_behavior(self):
  if UPSTREAM.exists():
   src=UPSTREAM.read_text()
   self.assertIn('DeveloperPortalProxy.shared.createCertificate(',src)
   self.assertIn('if isCustomCert {',src)
   self.assertIn('return activeCert',src)
if __name__=='__main__':unittest.main()
