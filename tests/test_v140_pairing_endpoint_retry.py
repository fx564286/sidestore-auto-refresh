"""V140 RemotePairing: host+port failover, one verification, rollback."""
from pathlib import Path
import importlib.util
import os
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v140rp',ROOT/'scripts/patch_v140_pairing_endpoint_retry.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class EndpointRecoveryTests(unittest.TestCase):
    def test_only_single_discovered_endpoint_is_verified(self):
        base='''// SCARLET_V138_RP_TYPED_UDID
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
        patched=v.wrapper(base)
        self.assertEqual(v.wrapper(patched),patched)
        self.assertIn('discovered.host == previousHost && discovered.port == previousPort',patched)
        self.assertIn('gateway.setDeviceEndpointIp(discovered.host)',patched)
        self.assertIn('gateway.setDeviceEndpointIp(previousHost)',patched)
        self.assertIn('gateway.setPort(previousPort, for: .rppairing)',patched)
        self.assertIn('lastV140BonjourRetryTime',patched)
        self.assertIn('UInt8(String($0)) != nil',patched)
        self.assertNotIn('remotePairingPortCache = newPort',patched)
        self.assertNotIn('resolveDiscoveredRemotePairingPortThrottled',patched)
    def test_endpoint_getter_preserves_original_record(self):
        base='''public protocol DeviceGatewayAPI: AnyObject, Sendable {
    var pairingFileType: PairingProtocol { get }
}'''
        result=v.api(base)
        self.assertIn('var deviceEndpointIp: String? { get }',result)
        self.assertEqual(v.api(result),result)
    def test_no_pairing_identity_mutations(self):
        s=(ROOT/'scripts/patch_v140_pairing_endpoint_retry.py').read_text()
        for unsafe in ('deletePairingFile(', 'reinitializePairingData(', 'SecItemDelete(',
                       'setPairingFileData(', 'wipeContainer(', 'keychain.reset('):
            self.assertNotIn(unsafe,s)
    def test_fail_closed(self):
        for fn in (v.wrapper,v.api):
            with self.assertRaises(ValueError):fn('unknown version')
    def test_generated_source_if_available(self):
        sidestore=os.getenv('V140_PATCHED_SIDESTORE')
        minimuxer=os.getenv('V140_PATCHED_MINIMUXER')
        if not sidestore or not minimuxer:return
        source=(Path(sidestore)/v.WRAPPER).read_text()
        api=(Path(minimuxer)/v.API).read_text()
        self.assertEqual(v.wrapper(source),source)
        self.assertEqual(v.api(api),api)
        self.assertEqual(source.count('SCARLET_V140_BONJOUR_ENDPOINT_RETRY'),1)
        self.assertIn('restore_original_endpoint',source)
if __name__=='__main__':unittest.main()
