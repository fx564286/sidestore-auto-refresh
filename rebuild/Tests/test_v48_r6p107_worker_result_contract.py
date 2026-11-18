"""P107: full P106 native result must survive host SideStoreSupport XPC."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
X=(R/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
W=(R/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
G=(R/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()

class P107NativeWorkerResultContract(unittest.TestCase):
    def test_success_case_is_whitelisted_and_accepted_only_on_true_callback(self):
        call='native_host_reinstall_returned_install_unverified'
        self.assertIn('"'+call+'",', X)
        self.assertIn('status == "'+call+'"', X.split('guard returned && (',1)[1].split(') else {',1)[0])
        self.assertIn('reply(true, "'+call+'")', W)
        self.assertIn('native_worker_operation_returned', (R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text())
        self.assertIn('"installation_verified": "false"', (R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text())
        self.assertNotIn('reply(true, "installed")',W)
    def test_failure_classification_is_exact_but_remains_failure(self):
        allowed=X.split('let allowed: Set<String> = [',1)[1].split(']',1)[0]
        for reason in ('host_selected_team_mismatch','selected_account_owner_unverified',
                       'team_operation_in_progress','host_selected_team_certificate_missing',
                       'host_registration_failed','host_bundle_path_unavailable',
                       'host_managed_owner_mismatch','host_managed_record_inactive'):
            self.assertIn('"'+reason+'",',allowed)
        self.assertIn('guard returned && (',X)
        self.assertIn('throw ScarletNativeRefreshFailure(reason: status',X)
        for reason in ('host_selected_team_mismatch','selected_account_owner_unverified',
                       'team_operation_in_progress'):
            self.assertIn('case "'+reason+'":',G)
    def test_unique_p107_build_and_release_identity(self):
        flow=(R/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
        self.assertIn('fix/scarlet-v48-r6p107-manual-result-contract-20261118',flow)
        self.assertIn('--host-build-version 3.8.107',flow)
        self.assertIn('Scarlet-Crystal-V48-R6P107-MANUAL-RESULT-UNSIGNED.ipa',flow)
        self.assertIn('scarlet-v48-r6p107-manual-result-unsigned-20261118',flow)
        self.assertIn('P107 native worker status fidelity symbols compiled in SideStoreSupport',flow)
    def test_original_signing_route_still_requires_selected_owner(self):
        self.assertIn('if manual, existingReason == nil,',W)
        self.assertIn('verifiedSameTeamManualHostURL(',W)
        self.assertIn('profile.teamIdentifier == teamID',W)
        self.assertIn('await ScarletInstallTeamAuthority.appBelongsToOwner(',W)
        self.assertIn('AppManager.shared.install(.url(installedHost)',W)
        self.assertNotIn('revokeCertificate(',W)
        self.assertNotIn('SecItemDelete(',W)
        self.assertIn('AppManager.shared.backgroundRefresh(',W)
if __name__=='__main__': unittest.main()
