"""V164 RP reset regression: verify actual generated source, retry ordering, no credential mutations."""
import importlib.util
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

def mod(file,name):
    s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m
v140=mod('patch_v140_pairing_endpoint_retry.py','v140fixture')
v142=mod('patch_v142_pairing_route_race.py','v142fixture')
v164=mod('patch_v164_rp_handshake_recovery.py','v164fixture')

class RPRecoverTests(unittest.TestCase):
    def fixture(self):
        orig='''// SCARLET_V138_RP_TYPED_UDID
private func resolveDiscoveredRemotePairingPort() async -> UInt16? {
    return nil
}
private var lastRemotePairingPortResolveTime: Date = .distantPast
private var activeRemotePairingPortResolveTask: Task<UInt16?, Never>?
private func resolveDiscoveredRemotePairingPortThrottled() async -> UInt16? {
    return nil
}
private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    do { return try await operation() } catch {
        remotePairingPortCache = newPort
        throw error
    }
}
public var minimuxerStatusPublisher: AnyPublisher<Result<Bool, Error>, Never> {
    minimuxer.core.statusPublisher
}'''
        return v142.wrapper(v140.wrapper(orig))

    def test_exact_v142_migration_idempotent(self):
        source=self.fixture()
        patched=v164.patch_source(source)
        self.assertEqual(v164.patch_source(patched),patched)
        self.assertNotEqual(patched,source)
        self.assertEqual(patched.count('// SCARLET_V164_TRANSPORT_RESYNC:'),1)
        self.assertEqual(patched.count('private func withRemotePairingRetry<T>'),1)
        self.assertIn('SCARLET_V142_NETWORK_GENERATION_GUARD',patched)

    def test_current_vpn_port_before_bonjour_host(self):
        source=v164.patch_source(self.fixture())
        vpn=source.index('candidates.append((initialHost, discovered.port, "vpn_peer_discovered_port"))')
        wifi=source.index('candidates.append((discovered.host, discovered.port, "bonjour_service_endpoint"))')
        self.assertLess(vpn,wifi)
        self.assertIn('candidates.prefix(3)',source)
        self.assertIn('try? await Task.sleep(nanoseconds: 250_000_000)',source)
        self.assertIn('message.contains("connectionreset")',source)
        self.assertIn('lastV140BonjourRetryTime',source)

    def test_no_fake_success_or_route_restore_after_handoff(self):
        source=v164.patch_source(self.fixture())
        for t in ('gateway.deviceEndpointIp == initialHost',
                  'gateway.getPort(for: .rppairing) == initialPort',
                  'gateway.deviceEndpointIp == expectedHost',
                  'stage=recovery decision=all_failed route=restored',
                  'stage=recovery decision=route_changed_no_restore',
                  'stage=auth decision=manual_repair record=preserved'):
            self.assertIn(t,source)
        self.assertIn('throw lastError',source)
        self.assertNotIn('return PairingFileManager.shared.pairingUDID',source)

    def test_never_delete_saved_data_or_fake_pairing(self):
        source=(ROOT/'scripts/patch_v164_rp_handshake_recovery.py').read_text()
        banned=('deletePairingFile(', 'SecItemDelete(', 'setPairingFileData(',
                'reinitializePairingData(', 'UserDefaults.standard.set(',
                'invalidateAllSigning(', 'removeProvisioningProfile(',
                'restartVPN(', 'refreshCertificate(', 'clearAllPairing(')
        for t in banned:self.assertNotIn(t,source)

    def test_wrong_input_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'requires V142'):
            v164.patch_source('old snapshot')

    def test_patched_real_generated_source(self):
        root=os.getenv('V164_PATCHED_SIDESTORE')
        if not root:return
        source=(Path(root)/v164.SOURCE).read_text()
        self.assertEqual(v164.patch_source(source),source)
        self.assertEqual(source.count('SCARLET_V164_TRANSPORT_RESYNC:'),1)
        self.assertIn('vpn_peer_discovered_port',source)
        self.assertIn('stage=recovery decision=all_failed',source)

if __name__=='__main__':unittest.main()
