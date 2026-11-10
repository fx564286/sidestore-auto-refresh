"""V27 recovery of actual SideStore native renewal, not just a timeout.

V26 iPhone diagnostic SourceCommit 12a916b228a4: worker managed count=1
and status=ready, followed ~1.08s later by SideStore NSError code=1.
Previously host RefreshAllAppsIntent was routed through a private intent
proxy before reaching actual SideStore. Now both manual+automatic routes
execute original AppManager.backgroundRefresh *inside* SideStore LiveProcess.
"""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
AGENT=(R/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
WIRE=(R/"integration/wire_scarlet_auth.py").read_text()
XPC=(R/"HostApp/ScarletAuthXPCSupport.swift").read_text()
MANUAL=(R/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
AUTO=(R/"HostApp/ScarletAutomaticRenewal.swift").read_text()
GLASS=(R/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
LEDGER=(R/"HostApp/ScarletGuestSessionLedger.swift").read_text()

class V27InProcessRefresh(unittest.TestCase):
    def test_guest_runs_original_appmanager_not_private_intent(self):
        self.assertIn('@objc static func perform(_ reply: @escaping (Bool, String) -> Void)', AGENT)
        self.assertIn('InstalledApp.fetchAppsForRefreshingAll(in: context)', AGENT)
        self.assertIn('AppManager.shared.backgroundRefresh(', AGENT)
        self.assertIn('operation.ignoresServerNotFoundError = false', AGENT)
        self.assertIn('continuation.resume(with: result)', AGENT)
        self.assertIn('continuation.resume(throwing: ScarletGuestRefreshDispatchError.noOperation)',AGENT)
        self.assertIn('let signedHostID = Bundle.Info.activeBundleIdentifier',AGENT)
        self.assertIn('$0.resignedBundleIdentifier == signedHostID',AGENT)
        self.assertIn('CertificateManager.shared.activeCertificate != nil',AGENT)
        self.assertIn('native_operation_returned_unverified',AGENT)
        self.assertIn('host_not_in_refresh_results',AGENT)
        self.assertIn('let hostResult = results[managedHost.bundleIdentifier]',AGENT)
        self.assertIn('host_not_in_refresh_results',XPC)
        self.assertIn('host_not_in_refresh_results',AUTO)
        self.assertNotIn('PrivateIntentRunner.run(',AGENT)

    def test_request_has_deduplicating_gate_and_categorized_failure(self):
        self.assertIn('private actor ScarletGuestNativeRefreshGate',AGENT)
        self.assertIn('guard await gate.claim() else',AGENT)
        self.assertIn('defer { Task { await gate.release() } }',AGENT)
        for reason in ('already_running','anisette_unavailable','vpn_unavailable',
                       'signing_failed','profile_refresh_failed','server_unavailable',
                       'installation_failed','sidestore_native_operation_failed'):
            self.assertIn(f'"{reason}"',AGENT)
        self.assertNotIn('reply(true, "installed")',AGENT)

    def test_xpc_sends_small_result_into_real_worker(self):
        self.assertIn('scarletPerformNativeRefresh:',WIRE)
        self.assertIn('NSClassFromString(@"ScarletGuestRefreshAgent")',WIRE)
        self.assertIn('respondsToSelector:@selector(perform:)',WIRE)
        self.assertIn('scarletPerformNativeRefresh',XPC)
        self.assertIn('private final class ScarletRefreshExecutionGate',XPC)
        self.assertIn('ScarletNativeAuthTransport.shared.prepare()',XPC)
        self.assertIn('native_operation_returned_unverified',XPC)
        self.assertIn('ScarletNativeRefreshFailure',XPC)

    def test_both_refresh_requests_use_same_worker(self):
        self.assertIn('let receipt = try await ScarletNativeRefreshExecutor.execute()',MANUAL)
        self.assertIn('let receipt = try await ScarletNativeRefreshExecutor.execute()',AUTO)
        self.assertNotIn('RefreshAllAppsIntent().perform()',MANUAL)
        self.assertNotIn('RefreshAllAppsIntent().perform()',AUTO)
        self.assertIn('native_worker_operation_returned',MANUAL)
        self.assertIn('automatic_native_worker_returned',AUTO)
        self.assertIn('installation_verified": "false"',MANUAL)
        self.assertIn('installation_verified": "false"',AUTO)
        self.assertIn('sidestore_managed_apps_inspected',MANUAL)
        self.assertIn('automatic_managed_apps_inspected',AUTO)

    def test_no_v26_glass_or_guest_data_regression(self):
        self.assertIn('glassPlate(radius: isOpen ? 28 : 31)',GLASS)
        self.assertIn('glass_morph_opened',GLASS)
        self.assertIn('glass_morph_closed',GLASS)
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V43"',LEDGER)
        self.assertIn('switch_target_boot_ack',LEDGER)
        self.assertNotIn('removePersistentDomain(',AGENT)
        self.assertNotIn('LCCertificateData',AGENT)
        self.assertNotIn('LCGuestData',AGENT)

if __name__=="__main__":unittest.main()
