"""P108: explicit imported certificate changes the HOST via native resign/installer.

The historical failure was not a bad DER read: the P107 on-device report
shows P12 import OK, then an informational mismatch and NO installer call.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
PANEL=(R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
SUPPORT=(R/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
WORKER=(R/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
WIRE=(R/'rebuild/integration/wire_scarlet_auth.py').read_text()
AUTO=(R/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
FLOW=(R/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class SelectedAccountCertificateHostResign(unittest.TestCase):
    def test_explicit_p12_import_triggers_real_host_replacement_not_only_warning(self):
        self.assertIn('"account_p12_imported"',PANEL)
        self.assertIn('case .different:',PANEL)
        after=PANEL.split('case .different:',1)[1].split('case .profileUnavailable:',1)[0]
        self.assertIn('await renewHostWithImportedSelectedCertificate(',after)
        self.assertIn('accountID: active.id, teamID: active.teamID',after)
        self.assertIn('ScarletInstalledProfileReadback.beginRequest(source: "selected_p12_rotation")',PANEL)
        self.assertIn('manual: true, certificateRotation: true',PANEL)
        self.assertIn('"selected_p12_host_resign_started"',PANEL)
        self.assertIn('"selected_p12_host_resign_failed"',PANEL)
        self.assertIn('installation_verified": "false"',PANEL)
    def test_exact_account_team_owner_and_old_host_profile_are_kept_separate(self):
        self.assertIn('rows.accounts.filter({ $0.active }).count == 1',PANEL)
        self.assertIn('$0.active && $0.id == accountID && $0.teamID == teamID',PANEL)
        self.assertIn('profile.teamIdentifier == teamID',WORKER)
        self.assertIn('ScarletInstallTeamAuthority.prepare(',WORKER)
        self.assertIn('installed.resignedBundleIdentifier == currentHostID',WORKER)
        self.assertIn('ScarletInstallTeamAuthority.appBelongsToOwner(',WORKER)
        self.assertIn('try await ScarletGuestDeviceTransport.ensureReady()',WORKER)
        self.assertNotIn('revokeCertificate(',WORKER)
        self.assertNotIn('SecItemDelete(',WORKER)
    def test_no_managed_app_inventory_shortcut_or_guest_signer_bypass(self):
        segment=WORKER.split('if rotateImportedCertificate {',1)[1].split('// Native SideStore keeps each InstalledApp',1)[0]
        self.assertIn('AppManager.shared.install(.url(installedHost)',segment)
        self.assertNotIn('InstalledApp.fetchAppsForRefreshingAll',segment)
        self.assertIn('AppManager.shared.refresh(',WORKER)
        self.assertIn('AppManager.shared.backgroundRefresh(',WORKER)
        self.assertIn('ScarletNativeRefreshExecutor.execute()',AUTO)
        self.assertIn('ScarletHostProvisioningSigner.check(',PANEL)
        self.assertIn('ScarletGuestSignerRecovery.trialExistingSideStoreCertificate(',PANEL)
    def test_xpc_selector_and_runtime_host_dispatch_distinct_from_manual_refresh(self):
        self.assertIn('scarletPerformSelectedHostResign:(NSString*)hostBundlePath',WIRE)
        self.assertIn('performCertificateRotationHostBundle:reply:',WIRE)
        self.assertIn('performSelectedHostBundle(hostBundlePath, manual: true,',WORKER)
        self.assertIn('rotateImportedCertificate: true, reply: reply)',WORKER)
        self.assertIn('client.scarletPerformSelectedHostResign(',SUPPORT)
        self.assertIn('client.scarletPerformManualNativeRefresh(',SUPPORT)
        self.assertIn('client.scarletPerformNativeRefresh(',SUPPORT)
    def test_expired_prior_host_profile_does_not_prohibit_provisioning_renewal(self):
        src=WORKER.split('func verifiedInstalledHostID(',1)[1].split('func ensure(',1)[0]
        self.assertNotIn('profile.expirationDate > Date()',src)
        self.assertIn('host.provisioningProfile',src)
        self.assertIn('profile.teamIdentifier == teamID',src)
    def test_independent_build_and_release(self):
        for marker in ['fix/scarlet-v48-r6p108-postimport-cert-rotation-20261118',
                       '--host-build-version 3.8.108',
                       'Scarlet-Crystal-V48-R6P108-P12-HOST-RESIGN-UNSIGNED.ipa',
                       'scarlet-v48-r6p108-p12-host-resign-unsigned-20261118']:
            self.assertIn(marker,FLOW)

if __name__=='__main__':unittest.main()
