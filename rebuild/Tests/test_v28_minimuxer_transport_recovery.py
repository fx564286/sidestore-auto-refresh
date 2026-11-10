"""V28: restore SideStore's ORIGINAL device transport before native refresh.

V27 iPhone diagnostic d510d53a90ff: one managed host / signing-ready,
then 1.1s later SideStoreSupport.ScarletNativeRefreshFailure(1) from the
real AppManager. V27 masked upstream Minimuxer/OperationError into a
single 'sidestore_native_operation_failed' opaque classification.

The embedded LiveProcess may not have executed SideStore AppDelegate's
AppBootManager.performBootSequence(), unlike a separately opened SideStore.
V28 must reuse only an existing saved pairing; never invent a new identity,
disable VPN, or claim a renewed Apple mobileprovision without readback.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
AGENT=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
XPC=(ROOT/"HostApp/ScarletAuthXPCSupport.swift").read_text()
AUTO=(ROOT/"HostApp/ScarletAutomaticRenewal.swift").read_text()
MANUAL=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
GLASS=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
LEDGER=(ROOT/"HostApp/ScarletGuestSessionLedger.swift").read_text()

class NativeDeviceTransportRecovery(unittest.TestCase):
    def test_original_sidestore_bootstrap_reuses_existing_pairing_only(self):
        self.assertIn('private enum ScarletGuestDeviceTransport',AGENT)
        self.assertIn('try await ensureMinimuxerReady()',AGENT)
        self.assertIn('PairingFileManager.shared.fetchPairingFile()',AGENT)
        self.assertIn('AppBootManager.shared.startMinimuxer(pairingFile: pairing)',AGENT)
        self.assertIn('syncMinimuxerBackendFromUserDefaults()',AGENT)
        self.assertIn('savedPairingUnavailable',AGENT)
        self.assertNotIn('PairingFileManager.shared.savePairingFile(',AGENT)
        self.assertNotIn('reinitializePairingData(',AGENT)
        self.assertNotIn('UserDefaults.standard.isPairingReset = false',AGENT)

    def test_transport_precedes_signing_pipeline(self):
        a=AGENT.index('let recoveredTransport = try await')
        b=AGENT.index('AppManager.shared.backgroundRefresh(',a)
        self.assertLess(a,b)
        self.assertIn('let managedHost = targets.first(where:',AGENT)
        self.assertIn('CertificateManager.shared.activeCertificate != nil',AGENT)
        self.assertIn('operation.ignoresServerNotFoundError = false',AGENT)
        self.assertIn('results[managedHost.bundleIdentifier] != nil',AGENT)
        self.assertIn('native_operation_returned_unverified_transport_recovered',AGENT)

    def test_original_upstream_typed_errors_not_hidden_by_string_classifier(self):
        self.assertIn('if let original = error as? OperationError',AGENT)
        for expected in ('.noDevice', '.noVPN', '.noConnection', '.notReachable',
                         '.pairingNotComplete', '.invalidPairingFile',
                         '.minimuxerNotStarted', '.notAuthenticated',
                         '.missingProvisioningProfile', '.missingAppGroup',
                         '.certificateExpired', '.certificateRevoked'):
            self.assertIn(expected,AGENT)
        for reason in ('pairing_file_missing','pairing_invalid',
                       'minimuxer_not_started','device_network_unavailable',
                       'device_endpoint_unavailable','sidestore_auth_missing'):
            self.assertIn(f'"{reason}"',AGENT)
            self.assertIn(f'"{reason}"',XPC)
            self.assertIn(f'case "{reason}"',AUTO)

    def test_guest_not_falsely_claimed_installed(self):
        self.assertIn('native_operation_returned_unverified',AGENT)
        self.assertIn('native_operation_returned_unverified_transport_recovered',XPC)
        self.assertIn('let receipt = try await ScarletNativeRefreshExecutor.execute()',AUTO)
        self.assertIn('let receipt = try await ScarletNativeRefreshExecutor.execute()',MANUAL)
        self.assertIn('installation_verified": "false"',AUTO)
        self.assertIn('installation_verified": "false"',MANUAL)
        self.assertNotIn('replaceItemAt(',AGENT)
        self.assertNotIn('installProvisioningProfiles(',AGENT)

    def test_v26_glass_and_recent_guest_sessions_unchanged(self):
        self.assertIn('glassPlate(radius: isOpen ? 28 : 31)',GLASS)
        self.assertIn('glass_morph_opened',GLASS)
        self.assertIn('glass_morph_closed',GLASS)
        self.assertIn('switch_target_boot_ack',LEDGER)
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V23"',LEDGER)

if __name__=="__main__":
    unittest.main()
