"""V172 contract: own-device RP advert is required; LAN host is never a VPN peer."""
from pathlib import Path
import importlib.util
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "v172_transport", BASE / "scripts/patch_v172_sideinstaller_transport.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

FIXTURE = '''import Foundation
// SCARLET_V164_TRANSPORT_RESYNC
// SCARLET_V170_RP_HANDSHAKE_RESET
private func resolveV140RemotePairingEndpoint() async -> (host: String, port: UInt16)? {
    return (host: resolved.host, port: resolved.port)
}
private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
        if let discovered,
           (discovered.host != initialHost || discovered.port != initialPort) {
            candidates.append((discovered.host, discovered.port, "bonjour_service_endpoint"))
        }
}
'''

class SideInstallerParity(unittest.TestCase):
    def test_own_ip_before_using_advertised_port(self):
        result = mod.patch(FIXTURE)
        self.assertEqual(result, mod.patch(result))
        self.assertEqual(result.count(mod.MARK), 1)
        self.assertIn("getifaddrs(&interfaces)", result)
        self.assertIn("inet_ntop(AF_INET", result)
        self.assertIn("scarletV172IsOwnAdvertisedIPv4(resolved.host)", result)
        self.assertLess(result.index("scarletV172IsOwnAdvertisedIPv4(resolved.host)"),
                        result.index("return (host: resolved.host, port: resolved.port)"))

    def test_do_not_dial_the_phones_wifi_address_as_rp_peer(self):
        result = mod.patch(FIXTURE)
        self.assertNotIn("bonjour_service_endpoint", result)
        self.assertIn("VPN peer", result)
        self.assertIn("port: resolved.port", result)

    def test_fail_closed_on_mismatched_generated_source(self):
        with self.assertRaises(ValueError):
            mod.patch("import Foundation\n")

    def test_preserve_credentials_and_pairing(self):
        script = (BASE / "scripts/patch_v172_sideinstaller_transport.py").read_text()
        for prohibited in ("deletePairingFile(", "SecItemDelete(", "savePairingFile(",
                           "setPairingFileData(", "refreshCertificate(", "removeApp("):
            self.assertNotIn(prohibited, script)

if __name__ == "__main__":
    unittest.main()
