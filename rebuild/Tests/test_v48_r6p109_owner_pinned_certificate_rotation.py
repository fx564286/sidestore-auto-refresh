"""P109 regression: original P108 native install pinned to host-import owner.

Source checks are NOT device execution or signing proof. The Apple signing
pipeline must be compiled independently by the macOS/Xcode workflow.
"""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
PANEL = (ROOT/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
XPC = (ROOT/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
WIRE = (ROOT/'rebuild/integration/wire_scarlet_auth.py').read_text()
WORKER = (ROOT/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
VAULT = (ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
AUTOMATIC = (ROOT/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
FLOW = (ROOT/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class RotationBoundToSelectedAccount(unittest.TestCase):
    def test_host_passes_exact_account_and_team_across_async_xpc(self):
        self.assertIn('selectedAccountID: accountID, selectedTeamID: teamID', PANEL)
        self.assertIn('selectedAccountID: String? = nil',XPC)
        self.assertIn('selectedTeamID: String? = nil',XPC)
        self.assertIn('accountID: selectedAccountID, teamID: selectedTeamID', XPC)
        self.assertIn('scarletPerformSelectedHostResign:(NSString*)hostBundlePath accountID:(NSString*)accountID teamID:(NSString*)teamID',WIRE)
        self.assertIn('performCertificateRotationHostBundle:accountID:teamID:reply:',WIRE)
        self.assertIn('hostBundlePath ?: @"", accountID ?: @"", teamID ?: @"", reply', WIRE)
    def test_worker_fails_closed_for_stale_host_owner(self):
        self.assertIn('@objc(performCertificateRotationHostBundle:accountID:teamID:reply:)',WORKER)
        segment = WORKER.split('if rotateImportedCertificate {',1)[1].split('// Native SideStore keeps each InstalledApp',1)[0]
        self.assertIn('guard let expectedOwner,',segment)
        self.assertIn('selectedAppleID.caseInsensitiveCompare(',segment)
        self.assertIn('selectedTeamID == expectedOwner.teamID',segment)
        self.assertIn('reply(false, "selected_account_owner_changed")', segment)
        self.assertIn('activeSelectedSignerSerial(',segment)
        self.assertIn('== pinnedSerial',segment)
        self.assertIn('installed, owner: expectedOwner',segment)
        self.assertIn('reply(false, "selected_account_signer_changed")',segment)
    def test_exact_signer_is_pinned_not_ambient_global(self):
        self.assertIn('static func activeSelectedSignerSerial(appleID: String,',VAULT)
        self.assertIn('matchingCertificate(for: teamID, appleID: appleID)',VAULT)
        self.assertIn('CertificateManager.shared.activeCertificate',VAULT)
        self.assertIn('return cert.serialNumber.lowercased()',VAULT)
        self.assertNotIn('SecItemDelete(',VAULT)
        self.assertNotIn('revokeCertificate(',VAULT)
    def test_original_refresh_and_other_runtime_unchanged(self):
        self.assertIn('client.scarletPerformManualNativeRefresh(',XPC)
        self.assertIn('client.scarletPerformNativeRefresh(',XPC)
        self.assertIn('AppManager.shared.install(.url(installedHost)',WORKER)
        self.assertIn('AppManager.shared.refresh(',WORKER)
        self.assertIn('AppManager.shared.backgroundRefresh(',WORKER)
        self.assertIn('ScarletNativeRefreshExecutor.execute()',AUTOMATIC)
        self.assertIn('installation_verified": "false"',PANEL)
    def test_unsigned_release_job_accepts_p109_push(self):
        gate = FLOW.split('publish-unsigned-github-release:', 1)[1].split('runs-on: ubuntu-24.04', 1)[0]
        self.assertIn("github.ref == 'refs/heads/fix/scarlet-v48-r6p109-owner-pinned-reinstall-20261118'", gate)
        self.assertIn("github.event_name == 'push'", gate)

    def test_version_and_native_release(self):
        for x in ('fix/scarlet-v48-r6p109-owner-pinned-reinstall-20261118',
                  '--host-build-version 3.8.109',
                  'Scarlet-Crystal-V48-R6P109-OWNER-PINNED-UNSIGNED.ipa',
                  'scarlet-v48-r6p109-owner-pinned-unsigned-20261118'):
            self.assertIn(x,FLOW)

if __name__ == '__main__': unittest.main()
