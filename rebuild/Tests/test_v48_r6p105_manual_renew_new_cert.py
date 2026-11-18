"""P105: exact-owner fresh-signing manual renewal, upstream auto behavior unchanged."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
REF=(R/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
WIRE=(R/'rebuild/integration/wire_scarlet_auth.py').read_text()
XPC=(R/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
PANEL=(R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
AUTO=(R/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
ISSUE=(R/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()

class ManualRenewFreshAccountSigner(unittest.TestCase):
    def test_existing_explicit_issue_is_still_force_new(self):
        self.assertIn('.issueFreshInstallCertificate(owner.teamID)',PANEL)
        self.assertIn('teamID: id, forceNew: true',ISSUE)
        self.assertIn('DeveloperPortalProxy.shared.createCertificate(',ISSUE)
        self.assertIn('return "ready_issued_apple"',ISSUE)
        self.assertNotIn('ready_existing_after_apple_issue_failed',ISSUE)
        self.assertIn('ScarletAccountVault.bindSignerSerial(',ISSUE)
    def test_native_manual_and_background_use_distinct_original_upstream_operations(self):
        self.assertIn('performSelectedHostBundle(hostBundlePath, manual: false, reply: reply)',REF)
        self.assertIn('performSelectedHostBundle(hostBundlePath, manual: true, reply: reply)',REF)
        self.assertIn('if manual {',REF)
        self.assertIn('AppManager.shared.refresh(',REF)
        self.assertIn('AppManager.shared.backgroundRefresh(',REF)
        self.assertIn('guard !targets.isEmpty else {',REF)
        self.assertIn('selectedAppleID',REF)
        self.assertIn('selectedTeamID',REF)
        self.assertIn('let teamState = await ScarletInstallTeamAuthority.prepare(',REF)
    def test_xpc_exports_and_calls_distinct_manual_dispatch(self):
        self.assertIn('scarletPerformManualNativeRefresh:(NSString*)hostBundlePath',WIRE)
        self.assertIn('performManualHostBundle:reply:',WIRE)
        self.assertIn('client.scarletPerformManualNativeRefresh(',XPC)
        self.assertIn('client.scarletPerformNativeRefresh(',XPC)
        self.assertIn('ScarletNativeRefreshExecutor.execute(manual: true)',PANEL)
        self.assertIn('ScarletNativeRefreshExecutor.execute()',AUTO)
    def test_host_registration_cache_cannot_keep_foreign_or_deleted_record(self):
        self.assertIn('let owner = await ScarletInstallTeamAuthority.activeOwnership()',REF)
        self.assertIn('return existing.isActive &&',REF)
        self.assertIn('existing.team?.identifier == owner.teamID',REF)
        self.assertIn('return "host_managed_owner_mismatch"',REF)
        self.assertIn('return existing.isActive ? "already_managed"',REF)
        self.assertIn('registered = false',REF)
        self.assertNotIn('clearActiveCertificate(',REF)
        self.assertNotIn('revokeCertificate(',REF)
    def test_no_fake_success_without_native_and_device_readback(self):
        self.assertIn('installation_verified": "false"',PANEL)
        self.assertIn('ScarletInstalledProfileReadback.beginRequest(source: "manual")',PANEL)
        self.assertIn('host_not_in_refresh_results',REF)
        self.assertIn('selected_team_not_in_refresh_results',REF)
if __name__=='__main__':unittest.main()
