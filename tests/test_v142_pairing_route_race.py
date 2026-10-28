"""V142 RemotePairing fallback is fail-closed on network reconfiguration."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(file,name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/file)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
v140=load('patch_v140_pairing_endpoint_retry.py','v140')
v142=load('patch_v142_pairing_route_race.py','v142')

class RouteRaceTests(unittest.TestCase):
    def _fixture(self):
        src='''// SCARLET_V138_RP_TYPED_UDID
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
        return v140.wrapper(src)

    def test_handoff_rejects_stale_route_after_async_dns(self):
        patched=v142.wrapper(self._fixture())
        self.assertEqual(v142.wrapper(patched),patched)
        self.assertIn('guard let peerBeforeDiscovery = gateway.deviceEndpointIp',patched)
        self.assertIn('guard gateway.deviceEndpointIp == peerBeforeDiscovery else',patched)
        self.assertIn('retry=network_handoff_skipped',patched)
        self.assertIn('if gateway.deviceEndpointIp == discovered.host &&',patched)
        self.assertIn('route_changed_not_restored',patched)
        self.assertIn('discovery=loopback_ignored',patched)
        self.assertEqual(patched.count(v142.MARK),1)

    def test_cannot_clear_or_recreate_pairing(self):
        s=(ROOT/'scripts/patch_v142_pairing_route_race.py').read_text()
        for banned in ('deletePairingFile(', 'SecItemDelete(', 'reinitializePairingData(',
                       'removeProvisioningProfile(', 'UserDefaults.standard.set(',
                       'removeApp(', 'restartVPN('):
            self.assertNotIn(banned,s)

    def test_fails_on_wrong_source(self):
        with self.assertRaises(ValueError):v142.wrapper('unrelated source')

    def test_checked_generated_source(self):
        root=os.getenv('V142_PATCHED_SIDESTORE')
        if not root:return
        src=(Path(root)/v142.SOURCE).read_text()
        self.assertEqual(v142.wrapper(src),src)
        self.assertEqual(src.count(v142.MARK),1)
        self.assertIn('network_handoff_skipped',src)
        self.assertIn('loopback_ignored',src)

if __name__=='__main__':unittest.main()
