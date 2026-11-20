"""P106 exact-owner external-signed installed host manual renewal source contracts."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
AG=(R/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
PN=(R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
AT=(R/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
XP=(R/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
class P106ManualOwnedHost(unittest.TestCase):
 def test_actual_installed_host_bundle_not_embedded_guest(self):
  self.assertIn('verifiedInstalledHostID(hostBundlePath: String)',AG)
  self.assertIn('let host = ALTApplication(fileURL: hostURL)',AG)
  self.assertIn('ownerSigner.x509.expiryDate > Date()',AG)
  self.assertIn('installedHostID',AG)
  self.assertNotIn('let signedHostID = Bundle.Info.activeBundleIdentifier',AG)
  self.assertIn('targets.first { $0.resignedBundleIdentifier == verified }',AG)
 def test_manual_zero_managed_reaches_native_same_owner_reinstall(self):
  self.assertIn('let manuallyOnboardableHost = nativeState.count == 0 &&',PN)
  self.assertIn('nativeState.reason == "no_managed_apps_for_selected_team"',PN)
  self.assertIn('guard nativeState.canRefreshSelectedTeam || manuallyOnboardableHost else {',PN)
  self.assertIn('if manual, existingReason == nil,',AG)
  self.assertIn('verifiedSameTeamManualHostURL(',AG)
  self.assertIn('profile.teamIdentifier == teamID',AG)
  self.assertIn('ScarletInstallTeamAuthority.hasValidSigningCertificate(',AG)
  self.assertIn('let teamState = await ScarletInstallTeamAuthority.prepare(',AG)
  self.assertIn('ScarletGuestDeviceTransport.ensureReady()',AG)
  self.assertIn('AppManager.shared.install(.url(installedHost)',AG)
  self.assertIn('await ScarletInstallTeamAuthority.appBelongsToOwner(',AG)
  self.assertIn('installed.resignedBundleIdentifier == verifiedHostID',AG)
  self.assertIn('native_host_reinstall_returned_install_unverified',AG)
 def test_automatic_never_self_installs_or_borrows_another_team(self):
  a=AG.split('guard !targets.isEmpty else {',1)[1].split('let signedHostID',1)[0]
  self.assertIn('if manual, existingReason == nil,',a)
  self.assertIn('hostBootstrap == "host_selected_team_mismatch"',a)
  self.assertIn('profile.teamIdentifier == teamID',AG)
  self.assertIn('ScarletNativeRefreshExecutor.execute()',AT)
  self.assertIn('guard nativeState.canRefreshSelectedTeam else {',AT)
  self.assertNotIn('AppManager.shared.install(',AT)
  self.assertNotIn('revokeCertificate(',AG)
  self.assertNotIn('SecItemDelete(',AG)
 def test_no_fake_ios_installation(self):
  self.assertIn('"native_host_reinstall_returned_install_unverified"',XP)
  self.assertIn('"native_host_reinstall_owner_unverified"',XP)
  self.assertIn('"native_host_reinstall_owner_unverified"',AT)
  self.assertIn('installation_verified": "false"',PN)
if __name__=="__main__": unittest.main()
